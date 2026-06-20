from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


APP_NAME = "MemeFinder"
APP_TITLE = "梗图搜查器"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}

DEFAULT_VISION_PROMPT = """你是一个“本地图片检索 DATA 生成器”，任务不是聊天，也不是评价图片，而是把图片转换成方便搜索的结构化记忆。

必须遵守：
1. 只输出一个合法 JSON 对象，不要输出 Markdown、解释段落、代码块或多余文字。
2. 不确定的内容用“可能”“疑似”标记，不要编造具体人物、组织、事件名称。
3. 不要做身份识别，不要判断真实个人身份。
4. 每个字段都要尽量写成用户会拿来搜索图片的词或短语。
5. 字段内容要详细，但不要长篇评论。数组建议 5 到 15 个短语。
6. 不要使用容易触发平台锁定的敏感历史词作为泛化标签；如果图片确实涉及某类背景，请改写为“相关时代氛围”“相关地点”“相关事件线索”“旧式宣传风格”“集体运动氛围”等更中性的检索词。

字段解释：
- image_text：图片里能看见的文字。尽量保留原文、换行、标点和明显错别字；没有文字就写空字符串。
- image_objects：画面中可见的对象、人物类型、物品、场景元素、UI 元素、表情、动作。不要只写一个大类，要拆成可搜索细节。
- image_structure：图片的组织形式和视觉结构，例如聊天截图、四格漫画、左右对比图、表格、新闻截图、海报、照片、截图套图、低清压缩表情包、黑底白字、顶部标题下方配图等。
- image_meaning：这张图可能被用户记住的概括性含义、情绪、用途和语境。这里最重要，要写“梗图、吐槽、讽刺、反转、阴阳怪气、尴尬、震惊、怀旧、地域氛围、校园氛围、职场氛围、游戏梗、影视梗、相关地点、相关事件线索、旧式宣传风格”等可检索标签。

输出格式固定为：
{
  "image_text": "图片中所有可见文字；没有就写空字符串",
  "image_objects": ["对象1", "对象2", "对象3"],
  "image_structure": "结构、版式、风格的简洁描述",
  "image_meaning": ["概括标签1", "情绪或用途2", "地点/事件/氛围线索3"]
}

例子 1：如果是聊天截图表情包，image_objects 可包含“聊天气泡”“头像”“截图界面”，image_structure 可写“手机聊天截图，上下对话结构”，image_meaning 可包含“吐槽”“阴阳怪气”“社交尴尬”“可作回复图”。
例子 2：如果是带旧海报风格的图，image_objects 可包含“人物群像”“标语”“红色背景”，image_structure 可写“旧式宣传海报构图”，image_meaning 可包含“旧式宣传风格”“集体运动氛围”“年代感”“严肃口号反差”。
例子 3：如果是地点或事件相关截图，不要随便断言具体事件；image_meaning 可写“相关地点线索”“公共事件讨论氛围”“新闻截图感”“争议话题氛围”。

现在请分析图片并输出 JSON。"""


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative_path: str | Path) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", app_base_dir()))
    else:
        base = app_base_dir()
    return base / Path(relative_path)


def is_portable() -> bool:
    return (app_base_dir() / "portable.mode").exists()


def data_dir() -> Path:
    if is_portable():
        path = app_base_dir() / "data"
    else:
        appdata = os.environ.get("APPDATA") or str(Path.home())
        path = Path(appdata) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def database_path() -> Path:
    return data_dir() / "meme_finder.sqlite3"


def default_settings() -> Dict[str, Any]:
    return {
        "scope_mode": "whitelist",
        "roots": [],
        "excludes": [],
        "enable_automation": True,
        "enable_ocr": True,
        "enable_vision": False,
        "vision_endpoint": "https://api.openai.com/v1/chat/completions",
        "vision_model": "gpt-4o-mini",
        "vision_api_key": "",
        "vision_prompt": DEFAULT_VISION_PROMPT,
        "language": "zh",
        "language_selected": False,
        "search_limit": 200,
        "scope_presets": [
            {
                "name": "默认白名单",
                "kind": "whitelist",
                "include_subdirs": True,
                "directories": [],
            },
            {
                "name": "默认黑名单",
                "kind": "blacklist",
                "include_subdirs": True,
                "directories": [],
            },
        ],
        "advanced_scope_presets": [],
        "tag_datasets": [
            {
                "id": "default",
                "name": "默认数据集",
                "image_count": 0,
                "scope_preset_names": [],
                "created_at": "",
            }
        ],
    }


def load_settings() -> Dict[str, Any]:
    settings = default_settings()
    path = settings_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    return settings


def save_settings(settings: Dict[str, Any]) -> None:
    merged = default_settings()
    merged.update(settings)
    settings_path().write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
