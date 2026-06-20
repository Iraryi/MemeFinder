from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional


TEXT_FIELDS = [
    "file_name",
    "image_text",
    "image_objects",
    "image_structure",
    "image_meaning",
    "custom_notes",
]

STATUS_FIELDS = {
    "ocr_tagged": "INTEGER DEFAULT 0",
    "ai_tagged": "INTEGER DEFAULT 0",
    "manual_tagged": "INTEGER DEFAULT 0",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def tokenize(query: str) -> List[str]:
    query = query.strip().lower()
    if not query:
        return []
    parts = re.split(r"[^\w\u4e00-\u9fff]+", query)
    terms = [part for part in parts if part]
    return terms or [query]


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def init_db(self) -> None:
        with self._lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_hash TEXT,
                    size_bytes INTEGER,
                    mtime REAL,
                    width INTEGER,
                    height INTEGER,
                    image_text TEXT DEFAULT '',
                    image_objects TEXT DEFAULT '',
                    image_structure TEXT DEFAULT '',
                    image_meaning TEXT DEFAULT '',
                    custom_notes TEXT DEFAULT '',
                    llm_raw TEXT DEFAULT '',
                    indexed_at TEXT,
                    updated_at TEXT
                )
                """
            )
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_images_hash ON images(file_hash)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_images_name ON images(file_name)")
            existing = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(images)").fetchall()
            }
            for field, ddl in STATUS_FIELDS.items():
                if field not in existing:
                    self.conn.execute(f"ALTER TABLE images ADD COLUMN {field} {ddl}")
            self.conn.commit()

    def upsert_file(self, meta: Dict[str, Any]) -> int:
        stamp = now_iso()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO images (
                    path, file_name, file_hash, size_bytes, mtime, width, height,
                    indexed_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    file_name=excluded.file_name,
                    file_hash=excluded.file_hash,
                    size_bytes=excluded.size_bytes,
                    mtime=excluded.mtime,
                    width=excluded.width,
                    height=excluded.height,
                    indexed_at=excluded.indexed_at,
                    updated_at=excluded.updated_at
                """,
                (
                    meta["path"],
                    meta["file_name"],
                    meta.get("file_hash"),
                    meta.get("size_bytes"),
                    meta.get("mtime"),
                    meta.get("width"),
                    meta.get("height"),
                    stamp,
                    stamp,
                ),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT id FROM images WHERE path=?", (meta["path"],)).fetchone()
            return int(row["id"])

    def get_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM images WHERE path=?", (path,)).fetchone()
            return row_to_dict(row) if row else None

    def get_image(self, image_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
            return row_to_dict(row) if row else None

    def update_metadata(self, image_id: int, fields: Dict[str, Any]) -> None:
        allowed = {
            "image_text",
            "image_objects",
            "image_structure",
            "image_meaning",
            "custom_notes",
            "llm_raw",
            "ocr_tagged",
            "ai_tagged",
            "manual_tagged",
        }
        clean = {key: value for key, value in fields.items() if key in allowed}
        if not clean:
            return
        clean["updated_at"] = now_iso()
        assignments = ", ".join(f"{key}=?" for key in clean.keys())
        values = list(clean.values()) + [image_id]
        with self._lock:
            self.conn.execute(f"UPDATE images SET {assignments} WHERE id=?", values)
            self.conn.commit()

    def list_recent(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM images ORDER BY updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM images ORDER BY file_name COLLATE NOCASE").fetchall()
            return [row_to_dict(row) for row in rows]

    def search(self, query: str, limit: int = 200) -> List[Dict[str, Any]]:
        terms = tokenize(query)
        if not terms:
            rows = self.list_recent(limit)
            for row in rows:
                row["score"] = 0
            return rows

        with self._lock:
            all_rows = self.conn.execute("SELECT * FROM images").fetchall()
        ranked: List[Dict[str, Any]] = []
        weights = {
            "image_meaning": 6,
            "image_text": 4,
            "image_objects": 3,
            "custom_notes": 3,
            "image_structure": 2,
            "file_name": 1,
        }
        for sqlite_row in all_rows:
            row = row_to_dict(sqlite_row)
            aggregate = "\n".join(str(row.get(field) or "") for field in TEXT_FIELDS).lower()
            if not all(term in aggregate for term in terms):
                continue
            score = 0
            full_query = query.strip().lower()
            for field, weight in weights.items():
                text = str(row.get(field) or "").lower()
                if full_query and full_query in text:
                    score += weight * 4
                for term in terms:
                    score += text.count(term) * weight
            row["score"] = score
            ranked.append(row)
        ranked.sort(key=lambda item: (item["score"], item.get("updated_at") or ""), reverse=True)
        return ranked[:limit]

    def export_data(self, path: Path) -> None:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM images ORDER BY id").fetchall()
            payload = {
                "version": 1,
                "exported_at": now_iso(),
                "images": [row_to_dict(row) for row in rows],
            }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_data(self, path: Path) -> int:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        images = payload.get("images", [])
        if not isinstance(images, list):
            raise ValueError("导入文件格式不正确：images 不是列表")
        count = 0
        for item in images:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            meta = {
                "path": item["path"],
                "file_name": item.get("file_name") or Path(item["path"]).name,
                "file_hash": item.get("file_hash"),
                "size_bytes": item.get("size_bytes"),
                "mtime": item.get("mtime"),
                "width": item.get("width"),
                "height": item.get("height"),
            }
            image_id = self.upsert_file(meta)
            self.update_metadata(
                image_id,
                {
                    "image_text": item.get("image_text", ""),
                    "image_objects": item.get("image_objects", ""),
                    "image_structure": item.get("image_structure", ""),
                    "image_meaning": item.get("image_meaning", ""),
                    "custom_notes": item.get("custom_notes", ""),
                    "llm_raw": item.get("llm_raw", ""),
                    "ocr_tagged": int(bool(item.get("ocr_tagged", 0))),
                    "ai_tagged": int(bool(item.get("ai_tagged", 0))),
                    "manual_tagged": int(bool(item.get("manual_tagged", 0))),
                },
            )
            count += 1
        return count

    def delete_missing_paths(self, paths: Iterable[str]) -> int:
        keep = set(paths)
        with self._lock:
            rows = self.conn.execute("SELECT id, path FROM images").fetchall()
            removed = 0
            for row in rows:
                if row["path"] not in keep:
                    self.conn.execute("DELETE FROM images WHERE id=?", (row["id"],))
                    removed += 1
            self.conn.commit()
            return removed
