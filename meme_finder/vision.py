from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict


class VisionError(RuntimeError):
    pass


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _strip_code_fence(text: str) -> str:
    fence = chr(96) * 3
    stripped = text.strip()
    if not stripped.startswith(fence):
        return stripped
    stripped = stripped[len(fence) :].lstrip()
    if stripped.lower().startswith("json"):
        stripped = stripped[4:].lstrip()
    if stripped.endswith(fence):
        stripped = stripped[: -len(fence)]
    return stripped.strip()


def parse_model_json(text: str) -> Dict[str, str]:
    text = _strip_code_fence(text)
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    data = json.loads(text)
    return {
        "image_text": _as_text(data.get("image_text")),
        "image_objects": _as_text(data.get("image_objects")),
        "image_structure": _as_text(data.get("image_structure")),
        "image_meaning": _as_text(data.get("image_meaning")),
        "llm_raw": json.dumps(data, ensure_ascii=False),
    }


def analyze_image(image_path: Path, settings: Dict[str, Any]) -> Dict[str, str]:
    api_key = settings.get("vision_api_key") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise VisionError("未填写识图 API Key")

    endpoint = settings.get("vision_endpoint") or "https://api.openai.com/v1/chat/completions"
    model = settings.get("vision_model") or "gpt-4o-mini"
    prompt = settings.get("vision_prompt") or "请输出图片内容 JSON。"
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VisionError(f"识图接口返回 {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise VisionError(f"识图接口连接失败: {exc}") from exc

    data = json.loads(body)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError("识图接口返回格式不是 Chat Completions") from exc
    return parse_model_json(content)
