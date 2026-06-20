from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List


APP_TITLE = "Tag Data Editor - Experimental"
TEXT_FIELDS = ["image_text", "image_objects", "image_structure", "image_meaning", "custom_notes"]


LABELS = {
    "zh": {
        "open": "打开标签数据 JSON",
        "save_as": "另存为",
        "path_replace": "路径迁移",
        "old_prefix": "原目录前缀",
        "new_prefix": "新目录前缀",
        "apply_path": "批量替换路径",
        "find_replace": "字段查找替换",
        "field": "字段",
        "find": "查找",
        "replace": "替换为",
        "apply_text": "批量替换文本",
        "meaning_tags": "图片意义标签",
        "tag": "标签",
        "add_tag": "添加标签",
        "remove_tag": "删除标签",
        "cleanup": "清理",
        "remove_missing": "删除不存在文件记录",
        "copy_backup": "另存前创建 .bak 备份",
        "log": "操作记录 / 预览",
        "all_fields": "全部文本字段",
    },
    "en": {
        "open": "Open tag-data JSON",
        "save_as": "Save As",
        "path_replace": "Path migration",
        "old_prefix": "Old folder prefix",
        "new_prefix": "New folder prefix",
        "apply_path": "Replace path prefix",
        "find_replace": "Find and replace fields",
        "field": "Field",
        "find": "Find",
        "replace": "Replace with",
        "apply_text": "Replace text",
        "meaning_tags": "Image-meaning tags",
        "tag": "Tag",
        "add_tag": "Add tag",
        "remove_tag": "Remove tag",
        "cleanup": "Cleanup",
        "remove_missing": "Remove missing-file records",
        "copy_backup": "Create .bak before saving",
        "log": "Operation log / preview",
        "all_fields": "All text fields",
    },
}


def normalize_prefix(value: str) -> str:
    return value.strip().replace("/", "\\").rstrip("\\/")


def replace_prefix(path: str, old_prefix: str, new_prefix: str) -> str | None:
    old_norm = normalize_prefix(old_prefix)
    new_norm = normalize_prefix(new_prefix)
    current = str(path or "").replace("/", "\\")
    if not old_norm or not new_norm:
        return None
    current_lower = current.lower()
    old_lower = old_norm.lower()
    if current_lower == old_lower:
        return new_norm
    if current_lower.startswith(old_lower + "\\"):
        return new_norm + current[len(old_norm):]
    return None


def split_tags(value: str) -> List[str]:
    parts = re.split(r"[、,;；\n]+", value or "")
    return [part.strip() for part in parts if part.strip()]


def join_tags(tags: List[str]) -> str:
    return "、".join(dict.fromkeys(tag for tag in tags if tag))


class TagDataEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x680")
        self.minsize(860, 560)

        self.language = tk.StringVar(value="zh")
        self.payload: Dict[str, Any] | None = None
        self.path: Path | None = None
        self.backup_var = tk.BooleanVar(value=True)
        self.field_var = tk.StringVar(value="all")
        self.old_prefix_var = tk.StringVar()
        self.new_prefix_var = tk.StringVar()
        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.tag_var = tk.StringVar()

        self._build()
        if len(sys.argv) > 1:
            candidate = Path(sys.argv[1])
            if candidate.exists():
                self._load(candidate)

    def tr(self, key: str) -> str:
        return LABELS[self.language.get()].get(key, key)

    def _build(self) -> None:
        self.configure(bg="#f4f6fb")
        self.header = tk.Frame(self, bg="#ffffff", padx=14, pady=12)
        self.header.pack(fill=tk.X)
        tk.Label(self.header, text=APP_TITLE, bg="#ffffff", fg="#1d2636", font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        ttk.Combobox(self.header, textvariable=self.language, values=["zh", "en"], width=6, state="readonly").pack(side=tk.RIGHT)
        self.language.trace_add("write", lambda *_args: self._rebuild())

        self.body = tk.Frame(self, bg="#f4f6fb", padx=14, pady=14)
        self.body.pack(fill=tk.BOTH, expand=True)
        self._build_body()

    def _rebuild(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self._build_body()

    def _build_body(self) -> None:
        top = tk.Frame(self.body, bg="#f4f6fb")
        top.pack(fill=tk.X, pady=(0, 10))
        tk.Button(top, text=self.tr("open"), command=self.open_file, bg="#0b84d8", fg="white", relief=tk.FLAT, padx=12, pady=8).pack(side=tk.LEFT)
        tk.Button(top, text=self.tr("save_as"), command=self.save_as, bg="#eef3f8", fg="#1d2636", relief=tk.FLAT, padx=12, pady=8).pack(side=tk.LEFT, padx=8)
        tk.Checkbutton(top, text=self.tr("copy_backup"), variable=self.backup_var, bg="#f4f6fb").pack(side=tk.LEFT, padx=8)
        self.summary_var = tk.StringVar(value=self._summary_text())
        tk.Label(top, textvariable=self.summary_var, bg="#f4f6fb", fg="#6c7480").pack(side=tk.RIGHT)

        grid = tk.Frame(self.body, bg="#f4f6fb")
        grid.pack(fill=tk.X)
        self._path_panel(grid).grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))
        self._text_panel(grid).grid(row=0, column=1, sticky=tk.NSEW, padx=8)
        self._tag_panel(grid).grid(row=0, column=2, sticky=tk.NSEW, padx=(8, 0))
        for col in range(3):
            grid.columnconfigure(col, weight=1)

        cleanup = tk.Frame(self.body, bg="#ffffff", padx=12, pady=12, highlightbackground="#d9dee8", highlightthickness=1)
        cleanup.pack(fill=tk.X, pady=12)
        tk.Label(cleanup, text=self.tr("cleanup"), bg="#ffffff", fg="#1d2636", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        tk.Button(cleanup, text=self.tr("remove_missing"), command=self.remove_missing, bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(side=tk.LEFT, padx=12)

        tk.Label(self.body, text=self.tr("log"), bg="#f4f6fb", fg="#6c7480").pack(anchor=tk.W)
        self.log = tk.Text(self.body, height=15, wrap=tk.WORD, relief=tk.FLAT, bg="#ffffff", fg="#1d2636")
        self.log.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self._log("Experimental tool. Open an exported tag_data JSON first.")

    def _panel(self, title: str) -> tk.Frame:
        panel = tk.Frame(self.body, bg="#ffffff", padx=12, pady=12, highlightbackground="#d9dee8", highlightthickness=1)
        tk.Label(panel, text=title, bg="#ffffff", fg="#1d2636", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        return panel

    def _path_panel(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=12, pady=12, highlightbackground="#d9dee8", highlightthickness=1)
        tk.Label(panel, text=self.tr("path_replace"), bg="#ffffff", fg="#1d2636", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        for label, var in [(self.tr("old_prefix"), self.old_prefix_var), (self.tr("new_prefix"), self.new_prefix_var)]:
            tk.Label(panel, text=label, bg="#ffffff", fg="#6c7480").pack(anchor=tk.W, pady=(8, 0))
            tk.Entry(panel, textvariable=var, relief=tk.FLAT, bg="#f8fafc").pack(fill=tk.X, ipady=5)
        tk.Button(panel, text=self.tr("apply_path"), command=self.apply_path_replace, bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(anchor=tk.W, pady=(12, 0))
        return panel

    def _text_panel(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=12, pady=12, highlightbackground="#d9dee8", highlightthickness=1)
        tk.Label(panel, text=self.tr("find_replace"), bg="#ffffff", fg="#1d2636", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        tk.Label(panel, text=self.tr("field"), bg="#ffffff", fg="#6c7480").pack(anchor=tk.W, pady=(8, 0))
        values = [("all", self.tr("all_fields"))] + [(field, field) for field in TEXT_FIELDS]
        self.field_values = values
        box = ttk.Combobox(panel, textvariable=self.field_var, values=[label for _value, label in values], state="readonly")
        box.current(0)
        box.pack(fill=tk.X)
        tk.Label(panel, text=self.tr("find"), bg="#ffffff", fg="#6c7480").pack(anchor=tk.W, pady=(8, 0))
        tk.Entry(panel, textvariable=self.find_var, relief=tk.FLAT, bg="#f8fafc").pack(fill=tk.X, ipady=5)
        tk.Label(panel, text=self.tr("replace"), bg="#ffffff", fg="#6c7480").pack(anchor=tk.W, pady=(8, 0))
        tk.Entry(panel, textvariable=self.replace_var, relief=tk.FLAT, bg="#f8fafc").pack(fill=tk.X, ipady=5)
        tk.Button(panel, text=self.tr("apply_text"), command=self.apply_text_replace, bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(anchor=tk.W, pady=(12, 0))
        return panel

    def _tag_panel(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=12, pady=12, highlightbackground="#d9dee8", highlightthickness=1)
        tk.Label(panel, text=self.tr("meaning_tags"), bg="#ffffff", fg="#1d2636", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        tk.Label(panel, text=self.tr("tag"), bg="#ffffff", fg="#6c7480").pack(anchor=tk.W, pady=(8, 0))
        tk.Entry(panel, textvariable=self.tag_var, relief=tk.FLAT, bg="#f8fafc").pack(fill=tk.X, ipady=5)
        tk.Button(panel, text=self.tr("add_tag"), command=lambda: self.apply_tag("add"), bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(anchor=tk.W, pady=(12, 0))
        tk.Button(panel, text=self.tr("remove_tag"), command=lambda: self.apply_tag("remove"), bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(anchor=tk.W, pady=(6, 0))
        return panel

    def _summary_text(self) -> str:
        if not self.payload:
            return "No file loaded"
        images = self.payload.get("images", [])
        return f"{len(images)} images | {self.path.name if self.path else ''}"

    def _images(self) -> List[Dict[str, Any]]:
        if not self.payload:
            return []
        images = self.payload.get("images", [])
        return images if isinstance(images, list) else []

    def _log(self, message: str) -> None:
        if hasattr(self, "log"):
            self.log.insert(tk.END, message + "\n")
            self.log.see(tk.END)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(title=self.tr("open"), filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self._load(Path(path))

    def _load(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            images = payload.get("images")
            if not isinstance(images, list):
                raise ValueError("JSON does not contain an images list.")
            self.payload = payload
            self.path = path
            self.summary_var.set(self._summary_text())
            self._log(f"Loaded: {path} ({len(images)} images)")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def apply_path_replace(self) -> None:
        images = self._images()
        changed = 0
        samples: List[str] = []
        old = self.old_prefix_var.get()
        new = self.new_prefix_var.get()
        for item in images:
            updated = replace_prefix(str(item.get("path") or ""), old, new)
            if updated:
                original = item.get("path")
                item["path"] = updated
                item["file_name"] = Path(updated).name
                changed += 1
                if len(samples) < 5:
                    samples.append(f"{original} -> {updated}")
        self._log(f"Path prefix replace: {changed} records changed.")
        for sample in samples:
            self._log("  " + sample)

    def selected_fields(self) -> List[str]:
        label = self.field_var.get()
        for value, text in getattr(self, "field_values", []):
            if label == text:
                return TEXT_FIELDS if value == "all" else [value]
        return TEXT_FIELDS

    def apply_text_replace(self) -> None:
        find = self.find_var.get()
        replacement = self.replace_var.get()
        if not find:
            messagebox.showinfo(APP_TITLE, "Find text is empty.")
            return
        changed = 0
        for item in self._images():
            for field in self.selected_fields():
                value = str(item.get(field) or "")
                if find in value:
                    item[field] = value.replace(find, replacement)
                    changed += 1
        self._log(f"Text replace: {changed} field values changed.")

    def apply_tag(self, action: str) -> None:
        tag = self.tag_var.get().strip()
        if not tag:
            return
        changed = 0
        for item in self._images():
            tags = split_tags(str(item.get("image_meaning") or ""))
            if action == "add" and tag not in tags:
                tags.append(tag)
                item["image_meaning"] = join_tags(tags)
                changed += 1
            elif action == "remove" and tag in tags:
                item["image_meaning"] = join_tags([existing for existing in tags if existing != tag])
                changed += 1
        self._log(f"{action.title()} tag: {changed} records changed.")

    def remove_missing(self) -> None:
        images = self._images()
        before = len(images)
        kept = [item for item in images if Path(str(item.get("path") or "")).exists()]
        if self.payload is not None:
            self.payload["images"] = kept
        self.summary_var.set(self._summary_text())
        self._log(f"Removed missing-file records: {before - len(kept)}")

    def save_as(self) -> None:
        if not self.payload:
            messagebox.showinfo(APP_TITLE, "No JSON is loaded.")
            return
        initial = self.path.name if self.path else "tag_data_edited.json"
        target = filedialog.asksaveasfilename(title=self.tr("save_as"), initialfile=initial, defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not target:
            return
        target_path = Path(target)
        if self.backup_var.get() and target_path.exists():
            shutil.copy2(target_path, target_path.with_suffix(target_path.suffix + ".bak"))
        target_path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log(f"Saved: {target_path}")


def main() -> None:
    app = TagDataEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
