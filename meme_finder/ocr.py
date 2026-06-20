from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, List, Tuple


class OCRError(RuntimeError):
    pass


def _text_from_rapid_result(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, tuple) and raw:
        raw = raw[0]
    lines: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                text = item.get("text") or item.get("rec_text")
                if text:
                    lines.append(str(text))
            elif isinstance(item, (list, tuple)):
                if len(item) >= 2 and isinstance(item[1], str):
                    lines.append(item[1])
                elif len(item) >= 2 and isinstance(item[1], (list, tuple)) and item[1]:
                    lines.append(str(item[1][0]))
    return "\n".join(line.strip() for line in lines if line and line.strip())


@lru_cache(maxsize=1)
def _rapidocr_engine() -> Any:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise OCRError("未安装 rapidocr-onnxruntime") from exc
    return RapidOCR()


def extract_with_rapidocr(image_path: Path) -> str:
    engine = _rapidocr_engine()
    return _text_from_rapid_result(engine(str(image_path)))


def extract_with_tesseract(image_path: Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise OCRError("未安装 Pillow/pytesseract") from exc

    image = Image.open(image_path)
    try:
        return pytesseract.image_to_string(image, lang="chi_sim+eng").strip()
    except Exception:
        return pytesseract.image_to_string(image).strip()


def extract_text(image_path: Path) -> Tuple[str, str]:
    errors: List[str] = []
    had_success = False
    for name, func in (
        ("RapidOCR", extract_with_rapidocr),
        ("Tesseract", extract_with_tesseract),
    ):
        try:
            text = func(image_path)
            had_success = True
            if text:
                return text, name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if had_success:
        return "", "none"
    if errors:
        raise OCRError("；".join(errors))
    return "", "none"
