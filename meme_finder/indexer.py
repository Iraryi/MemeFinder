from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Event
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from .config import IMAGE_EXTENSIONS
from .ocr import OCRError, extract_text
from .storage import Store
from .vision import VisionError, analyze_image


ProgressCallback = Callable[[str], None]


def _entry_path(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("path") or "")
    return str(entry or "")


def _entry_recursive(entry: Any) -> bool:
    if isinstance(entry, dict):
        return bool(entry.get("include_subdirs", True))
    return True


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def is_inside(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(parent)]) == str(parent)
    except ValueError:
        return False


def _is_excluded(path: Path, excludes: list[tuple[Path, bool]]) -> bool:
    for excluded, recursive in excludes:
        if recursive and is_inside(path, excluded):
            return True
        if not recursive and (path == excluded or path.parent == excluded):
            return True
    return False


def iter_images(settings: Dict[str, Any]) -> Iterator[Path]:
    root_entries = [entry for entry in settings.get("roots", []) if _entry_path(entry)]
    exclude_entries = [entry for entry in settings.get("excludes", []) if _entry_path(entry)]
    excludes = [(_resolve(_entry_path(entry)), _entry_recursive(entry)) for entry in exclude_entries]
    for entry in root_entries:
        root = _resolve(_entry_path(entry))
        recursive = _entry_recursive(entry)
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in IMAGE_EXTENSIONS and not _is_excluded(root, excludes):
                yield root
            continue
        if not recursive:
            for path in root.iterdir():
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not _is_excluded(path, excludes):
                    yield path
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath).resolve()
            if _is_excluded(current, excludes):
                dirnames[:] = []
                continue
            for filename in filenames:
                path = current / filename
                if path.suffix.lower() in IMAGE_EXTENSIONS and not _is_excluded(path, excludes):
                    yield path


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_size(path: Path) -> Tuple[Optional[int], Optional[int]]:
    try:
        from PIL import Image
    except ImportError:
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None


def file_meta(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    width, height = image_size(path)
    return {
        "path": str(path),
        "file_name": path.name,
        "file_hash": sha1_file(path),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "width": width,
        "height": height,
    }


def index_library(
    store: Store,
    settings: Dict[str, Any],
    progress: Optional[ProgressCallback] = None,
    stop_event: Optional[Event] = None,
    force_rebuild: bool = False,
) -> Dict[str, int]:
    def report(message: str) -> None:
        if progress:
            progress(message)

    image_paths = list(dict.fromkeys(str(path) for path in iter_images(settings)))
    total = len(image_paths)
    stats = {"total": total, "indexed": 0, "ocr": 0, "vision": 0, "errors": 0}
    if not image_paths:
        report("没有找到图片。请先添加搜索根目录。")
        return stats

    automation = bool(settings.get("enable_automation", True))
    enable_ocr = automation and bool(settings.get("enable_ocr", True))
    enable_vision = automation and bool(settings.get("enable_vision", False))

    for index, raw_path in enumerate(image_paths, start=1):
        if stop_event and stop_event.is_set():
            report("已停止。")
            break
        path = Path(raw_path)
        report(f"[{index}/{total}] 记录 {path.name}")
        try:
            existing = store.get_by_path(str(path))
            meta = file_meta(path)
            changed = force_rebuild or not existing or existing.get("file_hash") != meta["file_hash"]
            image_id = store.upsert_file(meta)
            updates: Dict[str, str] = {}

            if enable_ocr and (changed or not (existing or {}).get("image_text")):
                try:
                    text, engine_name = extract_text(path)
                    if text:
                        updates["image_text"] = text
                        updates["ocr_tagged"] = 1
                        stats["ocr"] += 1
                        report(f"[{index}/{total}] OCR 完成：{path.name} ({engine_name})")
                except OCRError as exc:
                    report(f"[{index}/{total}] OCR 跳过：{exc}")

            if enable_vision and (changed or not (existing or {}).get("llm_raw")):
                try:
                    vision_data = analyze_image(path, settings)
                    for key, value in vision_data.items():
                        if value and (changed or not (existing or {}).get(key)):
                            updates[key] = value
                    updates["ai_tagged"] = 1
                    stats["vision"] += 1
                    report(f"[{index}/{total}] 识图完成：{path.name}")
                except VisionError as exc:
                    stats["errors"] += 1
                    report(f"[{index}/{total}] 识图失败：{exc}")

            if updates:
                store.update_metadata(image_id, updates)
            stats["indexed"] += 1
        except Exception as exc:
            stats["errors"] += 1
            report(f"[{index}/{total}] 处理失败：{path.name}：{exc}")
    report(
        f"完成：记录 {stats['indexed']} 张，OCR {stats['ocr']} 张，识图 {stats['vision']} 张，错误 {stats['errors']} 个。"
    )
    return stats
