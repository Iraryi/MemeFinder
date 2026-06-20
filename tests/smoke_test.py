from __future__ import annotations

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_finder.storage import Store
from meme_finder.indexer import iter_images
from meme_finder.vision import parse_model_json


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "test.sqlite3"
        fake_image = root / "meme.jpg"
        fake_image.write_bytes(b"not a real image")

        store = Store(db)
        image_id = store.upsert_file(
            {
                "path": str(fake_image),
                "file_name": fake_image.name,
                "file_hash": "abc",
                "size_bytes": fake_image.stat().st_size,
                "mtime": fake_image.stat().st_mtime,
                "width": None,
                "height": None,
            }
        )
        store.update_metadata(
            image_id,
            {
                "image_text": "不要回答 不要回答",
                "image_objects": "聊天窗口；人物",
                "image_structure": "截图",
                "image_meaning": "梗图；讽刺；阴阳怪气",
                "custom_notes": "测试备注",
                "ai_tagged": 1,
                "manual_tagged": 1,
            },
        )
        assert store.search("阴阳怪气")[0]["id"] == image_id
        assert store.search("不要回答")[0]["score"] > 0

        export_path = root / "export.json"
        store.export_data(export_path)
        store.close()

        imported = Store(root / "imported.sqlite3")
        assert imported.import_data(export_path) == 1
        imported_row = imported.search("讽刺")[0]
        assert imported_row["file_name"] == "meme.jpg"
        assert imported_row["ai_tagged"] == 1
        assert imported_row["manual_tagged"] == 1
        imported.close()

        parsed = parse_model_json(
            '{"image_text":"文字","image_objects":["猫","桌子"],"image_structure":"漫画","image_meaning":["梗图","吐槽"]}'
        )
        assert parsed["image_objects"] == "猫；桌子"
        assert "梗图" in parsed["image_meaning"]

        scope_root = root / "scope"
        scope_child = scope_root / "child"
        scope_child.mkdir(parents=True)
        (scope_root / "top.jpg").write_bytes(b"top")
        (scope_child / "nested.jpg").write_bytes(b"nested")
        no_sub = list(iter_images({"roots": [{"path": str(scope_root), "include_subdirs": False}], "excludes": []}))
        with_sub = list(iter_images({"roots": [{"path": str(scope_root), "include_subdirs": True}], "excludes": []}))
        assert len(no_sub) == 1
        assert len(with_sub) == 2

    print("smoke test ok")


if __name__ == "__main__":
    main()
