from __future__ import annotations

import os
import json
import queue
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, List, Optional

from .config import APP_TITLE, data_dir, database_path, load_settings, resource_path, save_settings
from .indexer import index_library
from .storage import Store


BG = "#f4f6fb"
SURFACE = "#ffffff"
CARD = "#ffffff"
LINE = "#d9dee8"
TEXT = "#1d2636"
MUTED = "#6c7480"
ACCENT = "#0b84d8"
ACCENT_DARK = "#0568ad"
ORANGE = "#e5a23b"
DARK = "#1f2227"
DARK_2 = "#2a2e35"
RIBBON = "#eef1f6"

FIELD_LABELS = {
    "image_text": "图片文字",
    "image_objects": "图片物体",
    "image_structure": "图片结构",
    "image_meaning": "图片意义",
    "custom_notes": "备注",
}

LANGUAGE_OPTIONS = {
    "zh": ("中文", "Chinese"),
    "en": ("English", "英文"),
}


def round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> None:
    radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    canvas.create_polygon(points, smooth=True, **kwargs)


def _wheel_units(event: Any) -> int:
    if getattr(event, "num", None) == 4:
        return -3
    if getattr(event, "num", None) == 5:
        return 3
    delta = getattr(event, "delta", 0)
    if delta:
        return -max(1, abs(delta) // 120) if delta > 0 else max(1, abs(delta) // 120)
    return 0


def bind_mousewheel(widget: tk.Widget, scroll_target: Any) -> None:
    def on_wheel(event: Any) -> str:
        units = _wheel_units(event)
        if units:
            scroll_target.yview_scroll(units, "units")
        return "break"

    def bind_tree(node: tk.Widget) -> None:
        node.bind("<MouseWheel>", on_wheel, add="+")
        node.bind("<Button-4>", on_wheel, add="+")
        node.bind("<Button-5>", on_wheel, add="+")
        for child in node.winfo_children():
            bind_tree(child)

    bind_tree(widget)


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event: Any = None) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            bg="#1e2430",
            fg="white",
            padx=10,
            pady=6,
            justify=tk.LEFT,
            font=("Microsoft YaHei UI", 9),
        )
        label.pack()

    def hide(self, _event: Any = None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class RoundedSearch(tk.Frame):
    def __init__(self, parent: tk.Widget, command: Callable[[str], None], width: int = 900, height: int = 62):
        super().__init__(parent, bg=BG, width=width, height=height)
        self.command = command
        self.width = width
        self.height = height
        self.placeholder = "输入以搜索"
        self.var = tk.StringVar(value=self.placeholder)
        self.canvas = tk.Canvas(self, width=width, height=height, bg=BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            relief=tk.FLAT,
            bd=0,
            bg=SURFACE,
            fg="#a0a5ad",
            insertbackground=TEXT,
            font=("Microsoft YaHei UI", 18),
        )
        self.entry.place(x=34, y=15, width=width - 150, height=34)
        self.button = tk.Canvas(self, width=96, height=height, bg=BG, highlightthickness=0, cursor="hand2")
        self.button.place(x=width - 96, y=0)
        self.button.bind("<Button-1>", lambda _event: self.submit())
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Return>", lambda _event: self.submit())
        self.bind("<Configure>", self._resize)
        self._draw()

    def _resize(self, event: Any) -> None:
        self.width = max(320, event.width)
        self.height = max(48, event.height)
        self.canvas.configure(width=self.width, height=self.height)
        self.button.configure(width=96, height=self.height)
        self.entry.place_configure(x=34, y=(self.height - 34) // 2, width=self.width - 150)
        self.button.place_configure(x=self.width - 96, y=0)
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        self.button.delete("all")
        round_rect(self.canvas, 3, 3, self.width - 3, self.height - 3, 28, fill=SURFACE, outline="#d7dbe3")
        round_rect(self.button, 0, 3, 94, self.height - 3, 28, fill=ACCENT, outline=ACCENT)
        self.button.create_text(48, self.height // 2, text="⌕", fill="white", font=("Segoe UI Symbol", 28))

    def _focus_in(self, _event: Any) -> None:
        if self.var.get() == self.placeholder:
            self.var.set("")
            self.entry.configure(fg=TEXT)

    def _focus_out(self, _event: Any) -> None:
        if not self.var.get().strip():
            self.var.set(self.placeholder)
            self.entry.configure(fg="#a0a5ad")

    def submit(self) -> None:
        query = self.var.get().strip()
        if query == self.placeholder:
            query = ""
        self.command(query)

    def set_query(self, query: str) -> None:
        self.var.set(query or self.placeholder)
        self.entry.configure(fg=TEXT if query else "#a0a5ad")


class HomeCard(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str,
        icon: str,
        command: Callable[[], None],
        width: int = 260,
        height: int = 142,
    ):
        super().__init__(parent, width=width, height=height, bg=BG, highlightthickness=0, cursor="hand2")
        self.title_text = title
        self.subtitle = subtitle
        self.icon = icon
        self.command = command
        self.width = width
        self.height = height
        self.hover = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", lambda _event: self.command())
        Tooltip(self, subtitle)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        fill = "#fdfefe" if not self.hover else "#eef7ff"
        outline = "#dbe1ea" if not self.hover else ACCENT
        round_rect(self, 2, 2, self.width - 2, self.height - 2, 20, fill=fill, outline=outline)
        round_rect(self, 18, 22, 90, 94, 20, fill="#eef3f8", outline="")
        self.create_text(54, 58, text=self.icon, fill=ACCENT, font=("Microsoft YaHei UI", 32, "bold"))
        self.create_text(110, 42, text=self.title_text, fill=TEXT, anchor=tk.W, font=("Microsoft YaHei UI", 16, "bold"))
        self.create_text(110, 76, text=self.subtitle, fill=MUTED, anchor=tk.W, width=self.width - 128, font=("Microsoft YaHei UI", 9))

    def _enter(self, _event: Any = None) -> None:
        self.hover = True
        self._draw()

    def _leave(self, _event: Any = None) -> None:
        self.hover = False
        self._draw()


class MemeFinderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.minsize(1060, 680)
        self.configure(bg=BG)
        self._window_icon_image: Optional[tk.PhotoImage] = None
        self._apply_window_icon()

        self.settings = load_settings()
        self.language = str(self.settings.get("language") or "zh")
        if self.language not in LANGUAGE_OPTIONS:
            self.language = "zh"
        self.title(APP_TITLE if self.language == "zh" else "MemeFinder")
        self._prompt_first_run_language_if_needed()

        self.store = Store(database_path())
        self.event_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None
        self.thumbnail_cache: Dict[tuple[str, int, int], Any] = {}
        self.current_activity = "home"
        self.selected_tab = "文件"
        self.manual_rows: List[Dict[str, Any]] = []
        self.manual_index = -1
        self.manual_expanded = False
        self.manual_view_var = tk.StringVar(value="图片")
        self.manual_browse_var = tk.StringVar(value="全部图片")
        self.manual_sort_var = tk.StringVar(value="创建时间")
        self.manual_folder_var = tk.StringVar(value="全部文件夹")
        self.hide_ai_var = tk.BooleanVar(value=False)
        self.hide_manual_var = tk.BooleanVar(value=False)
        self.only_unai_var = tk.BooleanVar(value=False)
        self.only_unmanual_var = tk.BooleanVar(value=False)
        self.advanced_scope_var = tk.StringVar(value="不限制范围")
        self.home_results_active = False
        self.current_image_id: Optional[int] = None
        self.status_var = tk.StringVar(value="就绪")
        self.batch_default_message = "等待开始。批量处理不会在启动时自动运行。"
        self.batch_last_message = self.batch_default_message
        self.batch_started_at = 0.0
        self.batch_status_var = tk.StringVar(value=self.batch_default_message)
        self._ensure_tag_datasets()

        self._build_shell()
        self._show_home()
        self.after(150, self._poll_events)

    def _set_language(self, language: str, mark_selected: bool = True) -> None:
        if language not in LANGUAGE_OPTIONS:
            language = "zh"
        self.language = language
        self.settings["language"] = language
        if mark_selected:
            self.settings["language_selected"] = True
        save_settings(self.settings)
        self.title(APP_TITLE if language == "zh" else "MemeFinder")

    def _prompt_first_run_language_if_needed(self) -> None:
        if self.settings.get("language_selected"):
            return

        self.withdraw()
        dialog = tk.Toplevel(self)
        dialog.title("选择语言 / Choose Language")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=SURFACE, padx=28, pady=24)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            frame,
            text="请选择语言 / Please choose a language",
            bg=SURFACE,
            fg=TEXT,
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            frame,
            text="这是正式软件首次启动的语言选择。\nThis is the first-run language choice for the main app.",
            bg=SURFACE,
            fg=MUTED,
            justify=tk.LEFT,
            wraplength=440,
        ).pack(anchor=tk.W, pady=(8, 18))

        button_row = tk.Frame(frame, bg=SURFACE)
        button_row.pack(fill=tk.X, pady=(4, 14))

        def choose(language: str) -> None:
            self._set_language(language, mark_selected=True)
            dialog.destroy()

        tk.Button(
            button_row,
            text="中文\nChinese",
            command=lambda: choose("zh"),
            bg=ACCENT,
            fg="white",
            relief=tk.FLAT,
            padx=34,
            pady=16,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Button(
            button_row,
            text="English\n英文",
            command=lambda: choose("en"),
            bg="#eef3f8",
            fg=TEXT,
            relief=tk.FLAT,
            padx=34,
            pady=16,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        tk.Label(
            frame,
            text="之后可在“设置 > 语言 / Language”中修改。\nYou can change this later in Settings > Language.",
            bg=SURFACE,
            fg=MUTED,
            justify=tk.LEFT,
            wraplength=440,
        ).pack(anchor=tk.W)

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("zh"))
        dialog.update_idletasks()
        width, height = 520, 300
        x = max(0, (dialog.winfo_screenwidth() - width) // 2)
        y = max(0, (dialog.winfo_screenheight() - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        self.wait_window(dialog)
        self.deiconify()

    def destroy(self) -> None:
        try:
            self.stop_event.set()
            self.store.close()
        finally:
            super().destroy()

    def _apply_window_icon(self) -> None:
        icon_path = resource_path(Path("assets") / "MemeFinder.ico")
        png_path = resource_path(Path("assets") / "MemeFinder.png")
        try:
            if png_path.exists():
                self._window_icon_image = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, self._window_icon_image)
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    def _build_shell(self) -> None:
        self.topbar = tk.Frame(self, bg="#fbfcfe", height=38, highlightbackground=LINE, highlightthickness=1)
        self.topbar.pack(side=tk.TOP, fill=tk.X)

        quick = tk.Frame(self.topbar, bg="#fbfcfe")
        quick.pack(side=tk.LEFT, padx=8)
        for text, tip, command in [
            ("主菜单", "回到主菜单", self._show_home),
            ("⟳", "刷新当前活动", self._refresh_current),
        ]:
            btn = tk.Button(quick, text=text, width=8 if text == "主菜单" else 3, relief=tk.FLAT, bg="#fbfcfe", fg=TEXT, command=command, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=1)
            Tooltip(btn, tip)

        self.tab_frame = tk.Frame(self.topbar, bg="#fbfcfe")
        self.tab_frame.pack(side=tk.LEFT, padx=12)
        self.tab_buttons: Dict[str, tk.Button] = {}
        for tab in ["任务", "视图", "设置"]:
            btn = tk.Button(
                self.tab_frame,
                text=tab,
                relief=tk.FLAT,
                bg="#fbfcfe",
                fg=TEXT,
                padx=16,
                command=lambda name=tab: self._select_ribbon_tab(name),
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT)
            self.tab_buttons[tab] = btn

        self.ribbon = tk.Frame(self, bg=RIBBON, height=92, highlightbackground=LINE, highlightthickness=1)
        self.ribbon.pack(side=tk.TOP, fill=tk.X)
        self.ribbon.pack_propagate(False)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.status_bar = tk.Label(self, textvariable=self.status_var, anchor=tk.W, bg="#eef1f6", fg=MUTED, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._select_ribbon_tab("任务")

    def _select_ribbon_tab(self, tab: str) -> None:
        self.selected_tab = tab
        for name, btn in self.tab_buttons.items():
            active = name == tab
            btn.configure(bg=ACCENT if active else "#fbfcfe", fg="white" if active else TEXT)
        self._build_ribbon(tab)

    def _build_ribbon(self, tab: str) -> None:
        for child in self.ribbon.winfo_children():
            child.destroy()
        definitions = {
            "任务": [
                ("当前任务", [("刷新", self._refresh_current), ("停止任务", self._stop_indexing)]),
            ],
            "视图": [
                ("浏览", [("图片", lambda: self._set_manual_view("图片")), ("列表", lambda: self._set_manual_view("列表"))]),
                ("侧栏", [("放大侧栏", self._toggle_manual_expand), ("刷新", self._refresh_current)]),
            ],
            "设置": [
                ("设置中心", [("语言 / Language", self._open_language_settings), ("自动化配置", self._open_automation_settings), ("数据管理", self._open_data_management), ("检索范围", self._open_scope_manager)]),
            ],
        }
        for group_title, buttons in definitions.get(tab, []):
            group = tk.Frame(self.ribbon, bg=RIBBON, padx=12)
            group.pack(side=tk.LEFT, fill=tk.Y)
            row = tk.Frame(group, bg=RIBBON)
            row.pack(side=tk.TOP, pady=(10, 2))
            for text, command in buttons:
                btn = tk.Button(
                    row,
                    text=text,
                    relief=tk.FLAT,
                    bg="#f8fafc",
                    fg=TEXT,
                    padx=10,
                    pady=8,
                    command=command,
                    cursor="hand2",
                )
                btn.pack(side=tk.LEFT, padx=3)
            tk.Label(group, text=group_title, bg=RIBBON, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side=tk.BOTTOM)
            tk.Frame(self.ribbon, width=1, bg=LINE).pack(side=tk.LEFT, fill=tk.Y, pady=12)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        self.thumbnail_cache.clear()

    def _show_home(self) -> None:
        self.current_activity = "home"
        self.home_results_active = False
        self._clear_content()
        home = tk.Frame(self.content, bg=BG)
        home.pack(fill=tk.BOTH, expand=True)

        self.home_search = RoundedSearch(home, self._home_search, width=920, height=62)
        self.home_search.place(relx=0.5, y=76, anchor=tk.N)

        self.home_cards_frame = tk.Frame(home, bg=BG)
        self.home_cards_frame.place(relx=0.5, y=246, anchor=tk.N)
        cards = [
            ("高级搜索", "组合关键词、含义、结构和黑名单过滤。", "⌕", self._show_advanced_search),
            ("批量标签", "批量 OCR 和 AI 识图，建立可搜索 DATA。", "AI", self._show_batch_label),
            ("手动标签", "逐张浏览图片，在右侧侧栏沉浸式标注。", "✎", self._show_manual_label),
        ]
        for title, desc, icon, command in cards:
            HomeCard(self.home_cards_frame, title, desc, icon, command).pack(side=tk.LEFT, padx=16)

        self.home_results_holder = tk.Frame(home, bg=BG)
        self.home_results_holder.place(x=28, y=104, relwidth=1, width=-56, relheight=1, height=-128)
        self.home_results_holder.lower()

    def _home_search(self, query: str) -> None:
        if not query:
            self.status_var.set("请输入关键词再搜索。")
            return
        if self.home_results_active:
            self.home_search.place_configure(y=10)
            self.home_cards_frame.place_forget()
            self.home_results_holder.lift()
            self._render_search_results(self.home_results_holder, query)
            return
        self.status_var.set("搜索中，界面正在切换...")
        steps = 14
        start_y = 76
        end_y = 10

        def step(i: int) -> None:
            t = i / steps
            y = int(start_y + (end_y - start_y) * t)
            self.home_search.place_configure(y=y)
            self.home_cards_frame.place_configure(relx=0.5 - 0.05 * i, y=246 + i * 5)
            if i < steps:
                self.after(16, lambda: step(i + 1))
            else:
                self.home_cards_frame.place_forget()
                self.home_results_holder.lift()
                self.home_results_active = True
                self._render_search_results(self.home_results_holder, query)

        step(0)

    def _render_search_results(self, parent: tk.Frame, query: str) -> None:
        for child in parent.winfo_children():
            child.destroy()
        rows = self.store.search(query, limit=int(self.settings.get("search_limit", 200)))
        header = tk.Frame(parent, bg=BG)
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header, text=f"搜索结果：{query}", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 16, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text=f"{len(rows)} 张图片", bg=BG, fg=MUTED).pack(side=tk.LEFT, padx=12)
        self._render_gallery(parent, rows, mode="图片", on_select=self._select_search_result, on_double_select=self._open_image_viewer)
        self.status_var.set(f"找到 {len(rows)} 条结果。")

    def _show_advanced_search(self) -> None:
        self.current_activity = "advanced"
        self._clear_content()
        frame = tk.Frame(self.content, bg=BG, padx=28, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        title_row = tk.Frame(frame, bg=BG)
        title_row.pack(fill=tk.X)
        tk.Label(title_row, text="高级搜索", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(side=tk.LEFT)
        tk.Label(frame, text="搜索活动只负责查找；检索范围和数据导入导出统一放在设置里。", bg=BG, fg=MUTED).pack(anchor=tk.W, pady=(2, 14))

        top = tk.Frame(frame, bg=BG)
        top.pack(fill=tk.X)
        search = RoundedSearch(top, lambda query: self._advanced_search(query, results), width=760, height=54)
        search.pack(side=tk.LEFT)
        options = tk.Frame(top, bg=BG)
        options.pack(side=tk.LEFT, padx=18)
        self.adv_text_var = tk.BooleanVar(value=True)
        self.adv_objects_var = tk.BooleanVar(value=True)
        self.adv_structure_var = tk.BooleanVar(value=True)
        self.adv_meaning_var = tk.BooleanVar(value=True)
        for label, var in [
            ("文字", self.adv_text_var),
            ("物体", self.adv_objects_var),
            ("结构", self.adv_structure_var),
            ("意义", self.adv_meaning_var),
        ]:
            tk.Checkbutton(options, text=label, variable=var, bg=BG, fg=TEXT, selectcolor=BG).pack(side=tk.LEFT, padx=4)

        below = tk.Frame(frame, bg=BG)
        below.pack(fill=tk.BOTH, expand=True, pady=18)
        left = self._advanced_scope_panel(below)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))
        results = tk.Frame(below, bg=BG)
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._render_search_results(results, "")

    def _advanced_search(self, query: str, parent: tk.Frame) -> None:
        rows = self.store.search(query, limit=int(self.settings.get("search_limit", 200)))
        rows = self._filter_rows_by_advanced_scope(rows)
        allowed_fields = []
        if self.adv_text_var.get():
            allowed_fields.append("image_text")
        if self.adv_objects_var.get():
            allowed_fields.append("image_objects")
        if self.adv_structure_var.get():
            allowed_fields.append("image_structure")
        if self.adv_meaning_var.get():
            allowed_fields.append("image_meaning")
        if query and allowed_fields:
            q = query.lower()
            rows = [row for row in rows if any(q in str(row.get(field) or "").lower() for field in allowed_fields)]
        for child in parent.winfo_children():
            child.destroy()
        tk.Label(parent, text=f"高级搜索结果：{len(rows)} 张", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor=tk.W, pady=(0, 8))
        self._render_gallery(parent, rows, mode="图片", on_select=self._open_manual_from_row)

    def _show_batch_label(self) -> None:
        self.current_activity = "batch"
        self._clear_content()
        frame = tk.Frame(self.content, bg=BG, padx=28, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        title_row = tk.Frame(frame, bg=BG)
        title_row.pack(fill=tk.X)
        tk.Label(title_row, text="批量标签", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(side=tk.LEFT)
        tk.Label(frame, text="批量活动负责建立 DATA：OCR 提取文字，AI 归纳物体、结构和意义。", bg=BG, fg=MUTED).pack(anchor=tk.W, pady=(2, 14))

        body = tk.Frame(frame, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)
        self._scope_summary_panel(body).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))

        right = tk.Frame(body, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        settings_card = tk.Frame(right, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=18, pady=16)
        settings_card.pack(fill=tk.X)
        self.batch_auto_var = tk.BooleanVar(value=bool(self.settings.get("enable_automation", True)))
        self.batch_ocr_var = tk.BooleanVar(value=bool(self.settings.get("enable_ocr", True)))
        self.batch_ai_var = tk.BooleanVar(value=bool(self.settings.get("enable_vision", False)))
        for text, var in [
            ("启用自动化分析", self.batch_auto_var),
            ("启用 OCR：记录图片文字", self.batch_ocr_var),
            ("启用 AI：记录图片物体、结构、意义", self.batch_ai_var),
        ]:
            tk.Checkbutton(settings_card, text=text, variable=var, bg=SURFACE, fg=TEXT, selectcolor=SURFACE).pack(anchor=tk.W, pady=3)
        tk.Button(settings_card, text="保存自动化设置", command=self._save_batch_settings, bg="#eef3f8", relief=tk.FLAT, padx=12, pady=8).pack(anchor=tk.W, pady=(10, 0))

        controls = tk.Frame(right, bg=BG)
        controls.pack(fill=tk.X, pady=16)
        self.batch_start_button = tk.Button(controls, text="开始批量建立 DATA", command=self._start_indexing, bg=ACCENT, fg="white", relief=tk.FLAT, padx=18, pady=10)
        self.batch_start_button.pack(side=tk.LEFT)
        tk.Button(controls, text="停止", command=self._stop_indexing, bg="#eef3f8", relief=tk.FLAT, padx=16, pady=10).pack(side=tk.LEFT, padx=8)
        self.batch_status_label = tk.Label(right, textvariable=self.batch_status_var, bg="#fff8e8", fg=TEXT, anchor=tk.W, padx=10, pady=8)
        self.batch_status_label.pack(fill=tk.X, pady=(0, 8))
        self.batch_log = tk.Text(right, height=18, wrap=tk.WORD, bg="#fbfcfe", fg=TEXT, relief=tk.FLAT)
        self.batch_log.pack(fill=tk.BOTH, expand=True)
        if self.worker and self.worker.is_alive():
            self._refresh_batch_status()
            self.batch_log.insert(tk.END, "批量任务仍在运行。上方状态条会持续显示运行时间和最新状态。\n")
        else:
            self.batch_log.insert(tk.END, self.batch_last_message + "\n")

    def _scope_panel(self, parent: tk.Widget, compact: bool) -> tk.Frame:
        panel = tk.Frame(parent, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12, width=330)
        panel.pack_propagate(False)
        if compact:
            panel.configure(width=300)
        tk.Label(panel, text="范围与黑名单", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(panel, text="搜索功能不使用白名单；批量标签从搜索根目录读取，并跳过黑名单。", bg=SURFACE, fg=MUTED, wraplength=270, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 10))
        tk.Label(panel, text="搜索根目录", bg=SURFACE, fg=MUTED).pack(anchor=tk.W)
        self.roots_list = tk.Listbox(panel, height=4, exportselection=False, relief=tk.FLAT, bg="#f8fafc")
        self.roots_list.pack(fill=tk.X, pady=4)
        tk.Label(panel, text="黑名单目录", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(8, 0))
        self.excludes_list = tk.Listbox(panel, height=4, exportselection=False, relief=tk.FLAT, bg="#f8fafc")
        self.excludes_list.pack(fill=tk.X, pady=4)
        row = tk.Frame(panel, bg=SURFACE)
        row.pack(fill=tk.X, pady=8)
        tk.Button(row, text="加根目录", command=self._add_root, relief=tk.FLAT, bg="#eef3f8").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="加黑名单", command=self._add_exclude, relief=tk.FLAT, bg="#eef3f8").pack(side=tk.LEFT, padx=2)
        tk.Button(row, text="移除", command=self._remove_selected_scope, relief=tk.FLAT, bg="#eef3f8").pack(side=tk.LEFT, padx=2)
        self._refresh_scope_lists()
        return panel

    def _scope_summary_panel(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(parent, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12, width=330)
        panel.pack_propagate(False)
        tk.Label(panel, text="当前检索范围", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(panel, text="目录、黑白名单预设、导入导出和重扫都在设置 > 检索范围里管理。", bg=SURFACE, fg=MUTED, wraplength=280, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 10))
        roots = self.settings.get("roots", [])
        excludes = self.settings.get("excludes", [])
        tk.Label(panel, text=f"搜索目录：{len(roots)} 个", bg=SURFACE, fg=TEXT).pack(anchor=tk.W, pady=3)
        tk.Label(panel, text=f"黑名单目录：{len(excludes)} 个", bg=SURFACE, fg=TEXT).pack(anchor=tk.W, pady=3)
        tk.Button(panel, text="打开检索范围设置", command=self._open_scope_manager, relief=tk.FLAT, bg=ACCENT, fg="white", padx=12, pady=8).pack(anchor=tk.W, pady=12)
        return panel

    def _advanced_presets(self) -> List[Dict[str, Any]]:
        presets = list(self.settings.get("advanced_scope_presets") or [])
        self.settings["advanced_scope_presets"] = presets
        return presets

    def _advanced_scope_panel(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(parent, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12, width=330)
        panel.pack_propagate(False)
        tk.Label(panel, text="高级搜索临时范围", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
        tk.Label(panel, text="这里的范围只影响高级搜索，不会改动总设置里的检索范围。", bg=SURFACE, fg=MUTED, wraplength=280, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 10))

        values = ["不限制范围"] + [preset.get("name", "未命名范围") for preset in self._advanced_presets()]
        if self.advanced_scope_var.get() not in values:
            self.advanced_scope_var.set("不限制范围")
        box = ttk.Combobox(panel, textvariable=self.advanced_scope_var, values=values, state="readonly")
        box.pack(fill=tk.X, pady=(0, 8))

        def refresh_box() -> None:
            new_values = ["不限制范围"] + [preset.get("name", "未命名范围") for preset in self._advanced_presets()]
            box.configure(values=new_values)
            if self.advanced_scope_var.get() not in new_values:
                self.advanced_scope_var.set("不限制范围")

        def new_temp(kind: str) -> None:
            self._edit_advanced_scope(None, refresh_box, kind=kind)

        def edit_current() -> None:
            index = self._advanced_scope_index()
            if index is None:
                messagebox.showinfo("未选择范围", "请先选择一个临时范围。")
                return
            self._edit_advanced_scope(index, refresh_box)

        def delete_current() -> None:
            index = self._advanced_scope_index()
            if index is None:
                return
            presets = self._advanced_presets()
            if messagebox.askyesno("删除临时范围", "确定删除这个高级搜索临时范围吗？"):
                del presets[index]
                self.settings["advanced_scope_presets"] = presets
                save_settings(self.settings)
                refresh_box()

        def import_global() -> None:
            presets = self._advanced_presets()
            for preset in self._ensure_scope_presets():
                copied = dict(preset)
                copied["name"] = "导入：" + str(preset.get("name", "全局范围"))
                copied["directories"] = [dict(entry) for entry in self._preset_directory_entries(preset)]
                presets.append(copied)
            self.settings["advanced_scope_presets"] = presets
            save_settings(self.settings)
            refresh_box()
            self.status_var.set("已把总设置里的检索范围导入为高级搜索临时范围。")

        for label, command in [
            ("新建临时白名单", lambda: new_temp("whitelist")),
            ("新建临时黑名单", lambda: new_temp("blacklist")),
            ("编辑当前", edit_current),
            ("删除当前", delete_current),
            ("从总设置导入", import_global),
        ]:
            tk.Button(panel, text=label, command=command, relief=tk.FLAT, bg="#eef3f8", fg=TEXT, padx=12, pady=7).pack(fill=tk.X, pady=3)
        return panel

    def _advanced_scope_index(self) -> Optional[int]:
        name = self.advanced_scope_var.get()
        if not name or name == "不限制范围":
            return None
        for index, preset in enumerate(self._advanced_presets()):
            if preset.get("name") == name:
                return index
        return None

    def _edit_advanced_scope(self, index: Optional[int], on_saved: Callable[[], None], kind: str = "whitelist") -> None:
        presets = self._advanced_presets()
        if index is None:
            preset = {"name": "高级临时白名单" if kind == "whitelist" else "高级临时黑名单", "kind": kind, "directories": []}
        else:
            preset = dict(presets[index])
            preset["directories"] = [dict(entry) for entry in self._preset_directory_entries(preset)]

        def save_wrapper() -> None:
            on_saved()

        self._edit_scope_like_preset(preset, presets, index, save_wrapper, title="编辑高级搜索临时范围", settings_key="advanced_scope_presets")

    def _row_in_entries(self, row: Dict[str, Any], entries: List[Dict[str, Any]], kind: str) -> bool:
        if not entries:
            return True
        path = Path(row.get("path") or "")
        matched = False
        for entry in entries:
            root = Path(entry.get("path", ""))
            recursive = bool(entry.get("include_subdirs", True))
            try:
                if recursive:
                    current = os.path.commonpath([str(path), str(root)]) == str(root)
                else:
                    current = path.parent == root
            except ValueError:
                current = False
            matched = matched or current
        return matched if kind == "whitelist" else not matched

    def _filter_rows_by_advanced_scope(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        index = self._advanced_scope_index()
        if index is None:
            return rows
        preset = self._advanced_presets()[index]
        entries = self._preset_directory_entries(preset)
        kind = str(preset.get("kind") or "whitelist")
        return [row for row in rows if self._row_in_entries(row, entries, kind)]

    def _edit_scope_like_preset(
        self,
        preset: Dict[str, Any],
        presets: List[Dict[str, Any]],
        index: Optional[int],
        on_saved: Callable[[], None],
        title: str,
        settings_key: str,
    ) -> None:
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("680x500")
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)
        name_var = tk.StringVar(value=preset.get("name", ""))
        kind_var = tk.StringVar(value="白名单" if preset.get("kind") == "whitelist" else "黑名单")

        form = tk.Frame(frame, bg=SURFACE)
        form.pack(fill=tk.X)
        tk.Label(form, text="名称", bg=SURFACE, fg=MUTED).grid(row=0, column=0, sticky=tk.W, pady=5)
        tk.Entry(form, textvariable=name_var, relief=tk.FLAT, bg="#f8fafc").grid(row=0, column=1, sticky=tk.EW, padx=8, pady=5, ipady=5)
        tk.Label(form, text="类型", bg=SURFACE, fg=MUTED).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Combobox(form, textvariable=kind_var, values=["白名单", "黑名单"], state="readonly").grid(row=1, column=1, sticky=tk.W, padx=8, pady=5)
        form.columnconfigure(1, weight=1)

        tk.Label(frame, text="目录列表。编辑状态下双击目录行可切换是否包含子目录。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(12, 4))
        dir_tree = ttk.Treeview(frame, columns=("recursive",), show="tree headings", height=10)
        dir_tree.heading("#0", text="目录")
        dir_tree.heading("recursive", text="包含子目录")
        dir_tree.column("#0", width=500)
        dir_tree.column("recursive", width=110, anchor=tk.CENTER)
        dir_tree.pack(fill=tk.BOTH, expand=True)
        for entry in self._preset_directory_entries(preset):
            mark = "☑" if entry.get("include_subdirs", True) else "☐"
            dir_tree.insert("", tk.END, text=entry.get("path", ""), values=(mark,))

        row = tk.Frame(frame, bg=SURFACE)
        row.pack(fill=tk.X, pady=10)
        edit_mode = {"enabled": False}

        def add_dir() -> None:
            path = filedialog.askdirectory(title="添加目录")
            if path:
                dir_tree.insert("", tk.END, text=path, values=("☑",))

        def remove_dir() -> None:
            for selected in dir_tree.selection():
                dir_tree.delete(selected)

        def toggle_selected_recursive(_event: Any = None) -> None:
            if not edit_mode["enabled"]:
                return
            selected = dir_tree.selection()
            if not selected:
                return
            item_id = selected[0]
            current = dir_tree.item(item_id, "values")[0]
            dir_tree.item(item_id, values=("☐" if current == "☑" else "☑",))

        def toggle_edit_mode() -> None:
            edit_mode["enabled"] = not edit_mode["enabled"]
            edit_button.configure(text="确认" if edit_mode["enabled"] else "编辑包含子目录")

        def save() -> None:
            directories = []
            for item_id in dir_tree.get_children():
                values = dir_tree.item(item_id, "values")
                directories.append(
                    {
                        "path": dir_tree.item(item_id, "text"),
                        "include_subdirs": bool(values and values[0] == "☑"),
                    }
                )
            new_preset = {
                "name": name_var.get().strip() or "未命名预设",
                "kind": "whitelist" if kind_var.get() == "白名单" else "blacklist",
                "directories": directories,
            }
            if index is None:
                presets.append(new_preset)
            else:
                presets[index] = new_preset
            self.settings[settings_key] = presets
            save_settings(self.settings)
            if settings_key == "advanced_scope_presets":
                self.advanced_scope_var.set(new_preset["name"])
            on_saved()
            win.destroy()

        tk.Button(row, text="添加目录", command=add_dir, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(row, text="删除选中", command=remove_dir, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        edit_button = tk.Button(row, text="编辑包含子目录", command=toggle_edit_mode, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8)
        edit_button.pack(side=tk.LEFT, padx=4)
        tk.Button(row, text="保存", command=save, relief=tk.FLAT, bg=ACCENT, fg="white", padx=16, pady=8).pack(side=tk.RIGHT, padx=4)
        dir_tree.bind("<Double-1>", toggle_selected_recursive)

    def _show_manual_label(self) -> None:
        self.current_activity = "manual"
        self.manual_expanded = False
        self._clear_content()
        frame = tk.Frame(self.content, bg=BG, padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)
        header = tk.Frame(frame, bg=BG)
        header.pack(fill=tk.X)
        tk.Label(header, text="手动标签", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="浏览和编辑是同一活动；右侧侧栏可放大，按当前顺序上一个/下一个。", bg=BG, fg=MUTED).pack(side=tk.LEFT, padx=14)

        self.manual_main = tk.Frame(frame, bg=BG)
        self.manual_main.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.manual_browser = tk.Frame(self.manual_main, bg=BG)
        self.manual_browser.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.manual_editor = tk.Frame(self.manual_main, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12, width=390)
        self.manual_editor.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        self.manual_editor.pack_propagate(False)
        self._build_manual_browser()
        self._build_manual_editor()
        self._refresh_manual_browser()

    def _build_manual_browser(self) -> None:
        controls = tk.Frame(self.manual_browser, bg=BG)
        controls.pack(fill=tk.X, pady=(0, 10))
        for label, var, values in [
            ("呈现", self.manual_view_var, ["图片", "列表"]),
            ("浏览", self.manual_browse_var, ["全部图片", "按文件夹"]),
            ("排序", self.manual_sort_var, ["创建时间", "修改时间", "名称", "未手动标优先", "AI标注状态"]),
        ]:
            tk.Label(controls, text=label, bg=BG, fg=MUTED).pack(side=tk.LEFT, padx=(0, 3))
            box = ttk.Combobox(controls, textvariable=var, values=values, width=12, state="readonly")
            box.pack(side=tk.LEFT, padx=(0, 10))
            box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_manual_browser())

        tk.Checkbutton(controls, text="不看AI已标", variable=self.hide_ai_var, bg=BG, command=self._refresh_manual_browser).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(controls, text="不看已手动标", variable=self.hide_manual_var, bg=BG, command=self._refresh_manual_browser).pack(side=tk.LEFT, padx=4)
        tk.Button(controls, text="刷新", command=self._refresh_manual_browser, relief=tk.FLAT, bg="#eef3f8").pack(side=tk.RIGHT)

        self.folder_panel = tk.Frame(self.manual_browser, bg=BG)
        tk.Label(self.folder_panel, text="标签文件夹", bg=BG, fg=MUTED).pack(anchor=tk.W)
        self.folder_tree = ttk.Treeview(self.folder_panel, columns=("path",), displaycolumns=(), show="tree", height=7)
        self.folder_tree.pack(fill=tk.X, pady=(4, 8))
        self.folder_tree.bind("<<TreeviewSelect>>", self._select_manual_folder)
        bind_mousewheel(self.folder_tree, self.folder_tree)
        self._updating_folder_tree = False

        self.manual_body = tk.Frame(self.manual_browser, bg=BG)
        self.manual_body.pack(fill=tk.BOTH, expand=True)

    def _build_manual_editor(self) -> None:
        top = tk.Frame(self.manual_editor, bg=SURFACE)
        top.pack(fill=tk.X)
        tk.Label(top, text="编辑侧栏", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(side=tk.LEFT)
        self.expand_button = tk.Button(top, text="放大", command=self._toggle_manual_expand, relief=tk.FLAT, bg="#eef3f8")
        self.expand_button.pack(side=tk.RIGHT)

        self.manual_editor_canvas = tk.Canvas(self.manual_editor, bg=SURFACE, highlightthickness=0)
        self.manual_editor_scroll = ttk.Scrollbar(self.manual_editor, orient=tk.VERTICAL, command=self.manual_editor_canvas.yview)
        self.manual_editor_inner = tk.Frame(self.manual_editor_canvas, bg=SURFACE)
        self.manual_editor_inner_id = self.manual_editor_canvas.create_window((0, 0), window=self.manual_editor_inner, anchor=tk.NW)
        self.manual_editor_canvas.configure(yscrollcommand=self.manual_editor_scroll.set)
        self.manual_editor_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(10, 0))
        self.manual_editor_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(10, 0))

        def configure_editor_scroll(_event: Any = None) -> None:
            self.manual_editor_canvas.configure(scrollregion=self.manual_editor_canvas.bbox("all"))
            self.manual_editor_canvas.itemconfigure(self.manual_editor_inner_id, width=self.manual_editor_canvas.winfo_width())

        self.manual_editor_inner.bind("<Configure>", configure_editor_scroll)
        self.manual_editor_canvas.bind("<Configure>", configure_editor_scroll)

        self.manual_preview_frame = tk.Frame(self.manual_editor_inner, bg="#f0f3f8", height=190)
        self.manual_preview_frame.pack(fill=tk.X, pady=(0, 10))
        self.manual_preview_frame.pack_propagate(False)
        self.manual_preview = tk.Label(self.manual_preview_frame, text="未选择图片", bg="#f0f3f8", fg=MUTED, relief=tk.FLAT)
        self.manual_preview.place(x=0, y=0, relwidth=1, relheight=1)
        self.preview_zoom_button = tk.Button(
            self.manual_preview_frame,
            text="⤢",
            command=self._open_current_image_viewer,
            relief=tk.FLAT,
            bg="#ffffff",
            fg=ACCENT,
            font=("Segoe UI Symbol", 12, "bold"),
            cursor="hand2",
        )

        def show_zoom(_event: Any = None) -> None:
            self.preview_zoom_button.place(relx=1.0, x=-14, y=12, anchor=tk.NE, width=34, height=34)

        def hide_zoom(_event: Any = None) -> None:
            x = self.manual_preview_frame.winfo_pointerx() - self.manual_preview_frame.winfo_rootx()
            y = self.manual_preview_frame.winfo_pointery() - self.manual_preview_frame.winfo_rooty()
            if 0 <= x <= self.manual_preview_frame.winfo_width() and 0 <= y <= self.manual_preview_frame.winfo_height():
                return
            self.preview_zoom_button.place_forget()

        for widget in (self.manual_preview_frame, self.manual_preview, self.preview_zoom_button):
            widget.bind("<Enter>", show_zoom, add="+")
        self.manual_preview_frame.bind("<Leave>", hide_zoom, add="+")

        nav = tk.Frame(self.manual_editor_inner, bg=SURFACE)
        nav.pack(fill=tk.X, pady=(0, 8))
        tk.Button(nav, text="上一个", command=self._manual_prev, relief=tk.FLAT, bg="#eef3f8").pack(side=tk.LEFT)
        tk.Button(nav, text="下一个", command=self._manual_next, relief=tk.FLAT, bg=ACCENT, fg="white").pack(side=tk.LEFT, padx=8)
        tk.Button(nav, text="保存", command=self._save_current_metadata, relief=tk.FLAT, bg=ORANGE, fg="white").pack(side=tk.RIGHT)

        self.manual_status = tk.Label(self.manual_editor_inner, text="", bg=SURFACE, fg=MUTED, anchor=tk.W)
        self.manual_status.pack(fill=tk.X, pady=(0, 6))

        self.field_widgets: Dict[str, tk.Text] = {}
        fields = tk.Frame(self.manual_editor_inner, bg=SURFACE)
        fields.pack(fill=tk.BOTH, expand=True)
        for field, label in FIELD_LABELS.items():
            tk.Label(fields, text=label, bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(6, 0))
            height = 4 if field in {"image_text", "image_meaning"} else 3
            widget = tk.Text(fields, height=height, wrap=tk.WORD, relief=tk.FLAT, bg="#f8fafc", fg=TEXT)
            widget.pack(fill=tk.X)
            self.field_widgets[field] = widget
        bind_mousewheel(self.manual_editor_inner, self.manual_editor_canvas)

    def _select_manual_folder(self, _event: Any = None) -> None:
        if getattr(self, "_updating_folder_tree", False):
            return
        selection = self.folder_tree.selection() if hasattr(self, "folder_tree") else ()
        if not selection:
            return
        values = self.folder_tree.item(selection[0], "values")
        folder = values[0] if values else "全部文件夹"
        if folder != self.manual_folder_var.get():
            self.manual_folder_var.set(folder)
            self._refresh_manual_browser(refresh_folder_tree=False)

    def _populate_manual_folder_tree(self, folders: List[str]) -> None:
        if not hasattr(self, "folder_tree"):
            return
        self._updating_folder_tree = True
        try:
            tree = self.folder_tree
            tree.delete(*tree.get_children())
            tree.insert("", tk.END, iid="__all__", text="全部文件夹", values=("全部文件夹",), open=True)
            node_by_path: Dict[str, str] = {}

            def insert_path(path: Path) -> str:
                path_str = str(path)
                if path_str in node_by_path:
                    return node_by_path[path_str]
                parent = path.parent
                if parent == path:
                    parent_id = ""
                else:
                    parent_id = insert_path(parent)
                node_id = f"folder_{len(node_by_path)}"
                node_by_path[path_str] = node_id
                label = path.name or path_str
                tree.insert(parent_id, tk.END, iid=node_id, text=label, values=(path_str,), open=False)
                return node_id

            for folder in sorted(folders, key=lambda item: item.lower()):
                if folder and folder != "全部文件夹":
                    insert_path(Path(folder))

            selected = self.manual_folder_var.get()
            selected_id = "__all__"
            for path_str, node_id in node_by_path.items():
                if path_str == selected:
                    selected_id = node_id
                    break
            tree.selection_set(selected_id)
            tree.see(selected_id)
        finally:
            self._updating_folder_tree = False

    def _row_in_manual_folder(self, row: Dict[str, Any], folder: str) -> bool:
        if folder == "全部文件夹":
            return True
        try:
            image_folder = Path(row["path"]).parent.resolve()
            selected_folder = Path(folder).resolve()
            return os.path.commonpath([str(image_folder), str(selected_folder)]) == str(selected_folder)
        except (OSError, ValueError):
            return str(Path(row.get("path") or "").parent) == folder

    def _refresh_manual_browser(self, refresh_folder_tree: bool = True) -> None:
        if not hasattr(self, "manual_body"):
            return
        rows = self.store.list_all()
        folders = ["全部文件夹"] + sorted({str(Path(row["path"]).parent) for row in rows})
        if self.manual_folder_var.get() not in folders:
            self.manual_folder_var.set("全部文件夹")
        if self.manual_browse_var.get() == "按文件夹":
            if hasattr(self, "folder_panel") and not self.folder_panel.winfo_ismapped():
                self.folder_panel.pack(fill=tk.X, pady=(0, 8), before=self.manual_body)
            if refresh_folder_tree:
                self._populate_manual_folder_tree(folders)
            folder = self.manual_folder_var.get()
            if folder != "全部文件夹":
                rows = [row for row in rows if self._row_in_manual_folder(row, folder)]
        else:
            if hasattr(self, "folder_panel"):
                self.folder_panel.pack_forget()
            self.manual_folder_var.set("全部文件夹")
        if self.hide_ai_var.get() or self.only_unai_var.get():
            rows = [row for row in rows if not row.get("ai_tagged")]
        if self.hide_manual_var.get() or self.only_unmanual_var.get():
            rows = [row for row in rows if not row.get("manual_tagged")]
        sort_mode = self.manual_sort_var.get()
        if sort_mode == "名称":
            rows.sort(key=lambda row: str(row.get("file_name") or "").lower())
        elif sort_mode == "修改时间":
            rows.sort(key=lambda row: float(row.get("mtime") or 0), reverse=True)
        elif sort_mode == "AI标注状态":
            rows.sort(key=lambda row: (int(bool(row.get("ai_tagged"))), str(row.get("file_name") or "")))
        elif sort_mode == "未手动标优先":
            rows.sort(key=lambda row: (int(bool(row.get("manual_tagged"))), str(row.get("file_name") or "").lower()))
        else:
            rows.sort(key=lambda row: str(row.get("indexed_at") or ""), reverse=True)
        self.manual_rows = rows
        for child in self.manual_body.winfo_children():
            child.destroy()
        self._render_gallery(self.manual_body, rows, mode=self.manual_view_var.get(), on_select=self._select_manual_row)
        self.status_var.set(f"手动标签：当前浏览 {len(rows)} 张。")

    def _render_gallery(
        self,
        parent: tk.Frame,
        rows: List[Dict[str, Any]],
        mode: str,
        on_select: Callable[[Dict[str, Any]], None],
        on_double_select: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        if not rows:
            tk.Label(parent, text="没有图片记录。先到“批量标签”建立 DATA，或导入 DATA。", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 12)).pack(pady=40)
            return
        if mode == "列表":
            tree = ttk.Treeview(parent, columns=("meaning", "ai", "manual", "path"), show="tree headings")
            tree.heading("#0", text="文件")
            tree.heading("meaning", text="意义")
            tree.heading("ai", text="AI")
            tree.heading("manual", text="人工")
            tree.heading("path", text="路径")
            tree.column("#0", width=180)
            tree.column("meaning", width=220)
            tree.column("ai", width=60, anchor=tk.CENTER)
            tree.column("manual", width=70, anchor=tk.CENTER)
            tree.column("path", width=360)
            tree.pack(fill=tk.BOTH, expand=True)
            for row in rows:
                tree.insert(
                    "",
                    tk.END,
                    iid=str(row["id"]),
                    text=row.get("file_name") or Path(row["path"]).name,
                    values=(
                        str(row.get("image_meaning") or "")[:60],
                        "是" if row.get("ai_tagged") else "否",
                        "是" if row.get("manual_tagged") else "否",
                        row.get("path") or "",
                    ),
                )
            tree.bind("<<TreeviewSelect>>", lambda _event: self._tree_select(tree, rows, on_select))
            if on_double_select:
                tree.bind("<Double-1>", lambda _event: self._tree_select(tree, rows, on_double_select))
            bind_mousewheel(tree, tree)
            return

        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def configure_inner(_event: Any = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(inner_id, width=canvas.winfo_width())

        inner.bind("<Configure>", configure_inner)
        canvas.bind("<Configure>", configure_inner)
        bind_mousewheel(canvas, canvas)
        bind_mousewheel(inner, canvas)
        columns = 4
        for index, row in enumerate(rows):
            cell = tk.Frame(inner, bg=SURFACE, highlightbackground=LINE, highlightthickness=1, padx=8, pady=8, cursor="hand2")
            cell.grid(row=index // columns, column=index % columns, padx=8, pady=8, sticky=tk.NSEW)
            thumb = self._thumbnail(row.get("path") or "", 160, 112)
            if thumb:
                image_label = tk.Label(cell, image=thumb, bg=SURFACE)
                image_label.image = thumb
                image_label.pack()
            else:
                tk.Label(cell, text="无预览", bg="#edf1f6", fg=MUTED, width=20, height=6).pack()
            tk.Label(cell, text=row.get("file_name") or "", bg=SURFACE, fg=TEXT, wraplength=150).pack(fill=tk.X, pady=(6, 2))
            flags = []
            if row.get("ai_tagged"):
                flags.append("AI")
            if row.get("manual_tagged"):
                flags.append("人工")
            tk.Label(cell, text=" / ".join(flags) if flags else "未标签", bg=SURFACE, fg=MUTED).pack(anchor=tk.W)
            cell.bind("<Button-1>", lambda _event, item=row: on_select(item))
            if on_double_select:
                cell.bind("<Double-1>", lambda _event, item=row: on_double_select(item))
            for child in cell.winfo_children():
                child.bind("<Button-1>", lambda _event, item=row: on_select(item))
                if on_double_select:
                    child.bind("<Double-1>", lambda _event, item=row: on_double_select(item))
                bind_mousewheel(child, canvas)
            bind_mousewheel(cell, canvas)
        for col in range(columns):
            inner.columnconfigure(col, weight=1)

    def _tree_select(self, tree: ttk.Treeview, rows: List[Dict[str, Any]], on_select: Callable[[Dict[str, Any]], None]) -> None:
        selection = tree.selection()
        if not selection:
            return
        image_id = int(selection[0])
        for row in rows:
            if int(row["id"]) == image_id:
                on_select(row)
                return

    def _thumbnail(self, path: str, width: int, height: int) -> Any:
        key = (path, width, height)
        if key in self.thumbnail_cache:
            return self.thumbnail_cache[key]
        try:
            from PIL import Image, ImageTk

            with Image.open(path) as image:
                image.thumbnail((width, height))
                thumb = ImageTk.PhotoImage(image.copy())
            self.thumbnail_cache[key] = thumb
            return thumb
        except Exception:
            return None

    def _select_manual_row(self, row: Dict[str, Any]) -> None:
        self.current_image_id = int(row["id"])
        self.manual_index = next((index for index, item in enumerate(self.manual_rows) if int(item["id"]) == self.current_image_id), -1)
        for field, widget in self.field_widgets.items():
            widget.delete("1.0", tk.END)
            widget.insert("1.0", row.get(field) or "")
        self._load_manual_preview(row.get("path") or "")
        self.manual_status.configure(
            text=f"{self.manual_index + 1 if self.manual_index >= 0 else 0}/{len(self.manual_rows)}  AI：{'是' if row.get('ai_tagged') else '否'}  人工：{'是' if row.get('manual_tagged') else '否'}"
        )

    def _open_manual_from_row(self, row: Dict[str, Any]) -> None:
        self._show_manual_label()
        self._select_manual_row(row)

    def _select_search_result(self, row: Dict[str, Any]) -> None:
        self.status_var.set(f"已选中：{row.get('file_name') or Path(row.get('path') or '').name}；双击可打开查看窗口。")

    def _open_image_viewer(self, row: Dict[str, Any]) -> None:
        path = Path(row.get("path") or "")
        if not path.exists():
            messagebox.showwarning("图片不存在", "找不到这张图片的原文件。")
            return
        win = tk.Toplevel(self)
        win.title(path.name)
        win.geometry("980x720")
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(frame, bg=SURFACE)
        header.pack(fill=tk.X)
        tk.Label(header, text=path.name, bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 15, "bold")).pack(side=tk.LEFT)
        tk.Label(frame, text=str(path), bg=SURFACE, fg=MUTED, anchor=tk.W, wraplength=900).pack(fill=tk.X, pady=(4, 10))

        image_box = tk.Frame(frame, bg="#f0f3f8", height=540)
        image_box.pack(fill=tk.BOTH, expand=True)
        image_label = tk.Label(image_box, bg="#f0f3f8", fg=MUTED)
        image_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        thumb = self._thumbnail(str(path), 920, 520)
        if thumb:
            image_label.configure(image=thumb, text="")
            image_label.image = thumb
        else:
            image_label.configure(text="无法预览这张图片")

        buttons = tk.Frame(frame, bg=SURFACE)
        buttons.pack(fill=tk.X, pady=(12, 0))

        def open_folder() -> None:
            os.startfile(str(path.parent))

        def save_as() -> None:
            target = filedialog.asksaveasfilename(
                title="另存图片",
                initialfile=path.name,
                defaultextension=path.suffix,
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.tif;*.tiff"), ("所有文件", "*.*")],
            )
            if target:
                shutil.copy2(path, target)
                self.status_var.set(f"图片已另存到：{target}")

        tk.Button(buttons, text="打开所在目录", command=open_folder, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="另存图片", command=save_as, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="关闭", command=win.destroy, relief=tk.FLAT, bg=ACCENT, fg="white", padx=14, pady=8).pack(side=tk.RIGHT, padx=4)

    def _open_current_image_viewer(self) -> None:
        if self.current_image_id is None:
            return
        row = self.store.get_image(self.current_image_id)
        if row:
            self._open_image_viewer(row)

    def _load_manual_preview(self, path: str) -> None:
        if hasattr(self, "manual_preview_frame"):
            self.manual_preview_frame.configure(height=280 if self.manual_expanded else 190)
        size = (720, 260) if self.manual_expanded else (320, 170)
        thumb = self._thumbnail(path, size[0], size[1])
        if thumb:
            self.manual_preview.configure(image=thumb, text="")
            self.manual_preview.image = thumb
        else:
            self.manual_preview.configure(image="", text=Path(path).name if path else "未选择图片")

    def _manual_prev(self) -> None:
        if not self.manual_rows:
            return
        if self.manual_index <= 0:
            self.manual_index = len(self.manual_rows) - 1
        else:
            self.manual_index -= 1
        self._select_manual_row(self.manual_rows[self.manual_index])

    def _manual_next(self) -> None:
        if self.current_activity != "manual":
            self._show_manual_label()
            return
        if not self.manual_rows:
            return
        self.manual_index = (self.manual_index + 1) % len(self.manual_rows)
        self._select_manual_row(self.manual_rows[self.manual_index])

    def _toggle_manual_expand(self) -> None:
        if self.current_activity != "manual" or not hasattr(self, "manual_browser"):
            return
        self.manual_expanded = not self.manual_expanded
        if self.manual_expanded:
            self.manual_browser.pack_forget()
            self.manual_editor.pack_forget()
            self.manual_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.manual_editor.configure(width=900)
            self.expand_button.configure(text="退出沉浸")
        else:
            self.manual_editor.pack_forget()
            self.manual_browser.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.manual_editor.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
            self.manual_editor.configure(width=390)
            self.expand_button.configure(text="放大")
        row = self.store.get_image(self.current_image_id) if self.current_image_id else None
        if row:
            self._load_manual_preview(row.get("path") or "")

    def _save_current_metadata(self) -> None:
        if self.current_image_id is None:
            messagebox.showinfo("没有选择图片", "请先选择一张图片。")
            return
        fields = {field: widget.get("1.0", tk.END).strip() for field, widget in self.field_widgets.items()}
        fields["manual_tagged"] = 1
        self.store.update_metadata(self.current_image_id, fields)
        self.status_var.set("已保存人工标签。")
        self._refresh_manual_browser()

    def _set_manual_view(self, mode: str) -> None:
        self.manual_view_var.set(mode)
        if self.current_activity == "manual":
            self._refresh_manual_browser()

    def _save_batch_settings(self) -> None:
        self.settings["enable_automation"] = self.batch_auto_var.get()
        self.settings["enable_ocr"] = self.batch_ocr_var.get()
        self.settings["enable_vision"] = self.batch_ai_var.get()
        save_settings(self.settings)
        self.status_var.set("批量标签设置已保存。")

    def _format_elapsed(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"

    def _refresh_batch_status(self) -> None:
        running = bool(self.worker and self.worker.is_alive())
        if running:
            elapsed = self._format_elapsed(time.time() - self.batch_started_at)
            text = f"批量任务正在运行 {elapsed}｜最新状态：{self.batch_last_message}"
        else:
            text = self.batch_last_message
        self.batch_status_var.set(text)

    def _set_batch_status(self, message: str, update_bottom: bool = True) -> None:
        self.batch_last_message = message
        self._refresh_batch_status()
        if update_bottom:
            self.status_var.set(message)

    def _tick_batch_status(self) -> None:
        if self.worker and self.worker.is_alive():
            self._refresh_batch_status()
            self.after(1000, self._tick_batch_status)

    def _start_indexing(self, force_rebuild: bool = False) -> None:
        if hasattr(self, "batch_auto_var"):
            self._save_batch_settings()
        if self.worker and self.worker.is_alive():
            return
        if not self.settings.get("roots"):
            messagebox.showinfo("需要搜索范围", "请先添加至少一个搜索根目录。")
            return
        self.stop_event.clear()
        self.batch_started_at = time.time()
        self._set_batch_status("任务已启动，正在扫描图片...")
        if hasattr(self, "batch_log"):
            self.batch_log.insert(tk.END, "开始批量处理。\n")
            self.batch_log.see(tk.END)

        def target() -> None:
            try:
                stats = index_library(
                    self.store,
                    self.settings,
                    progress=lambda message: self.event_queue.put(("status", message)),
                    stop_event=self.stop_event,
                    force_rebuild=force_rebuild,
                )
                self.event_queue.put(("done", stats))
            except Exception as exc:
                self.event_queue.put(("error", str(exc)))

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()
        self._tick_batch_status()

    def _stop_indexing(self) -> None:
        self.stop_event.set()
        self._set_batch_status("正在停止批量任务...")

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                if event == "status":
                    self._set_batch_status(str(payload))
                    if hasattr(self, "batch_log"):
                        self.batch_log.insert(tk.END, str(payload) + "\n")
                        self.batch_log.see(tk.END)
                elif event == "done":
                    self._set_batch_status("批量 DATA 更新完成。")
                    self.batch_started_at = 0.0
                    if self.current_activity == "manual":
                        self._refresh_manual_browser()
                elif event == "error":
                    messagebox.showerror("处理失败", str(payload))
                    self._set_batch_status("任务失败。")
                    self.batch_started_at = 0.0
        except queue.Empty:
            pass
        self.after(150, self._poll_events)

    def _add_root(self) -> None:
        path = filedialog.askdirectory(title="选择搜索根目录")
        if not path:
            return
        roots = list(self.settings.get("roots", []))
        if path not in roots:
            roots.append(path)
        self.settings["roots"] = roots
        save_settings(self.settings)
        self._refresh_scope_lists()

    def _add_exclude(self) -> None:
        path = filedialog.askdirectory(title="选择黑名单目录")
        if not path:
            return
        excludes = list(self.settings.get("excludes", []))
        if path not in excludes:
            excludes.append(path)
        self.settings["excludes"] = excludes
        save_settings(self.settings)
        self._refresh_scope_lists()

    def _remove_selected_scope(self) -> None:
        roots = list(self.settings.get("roots", []))
        excludes = list(self.settings.get("excludes", []))
        if hasattr(self, "roots_list"):
            for index in reversed(self.roots_list.curselection()):
                if index < len(roots):
                    del roots[index]
        if hasattr(self, "excludes_list"):
            for index in reversed(self.excludes_list.curselection()):
                if index < len(excludes):
                    del excludes[index]
        self.settings["roots"] = roots
        self.settings["excludes"] = excludes
        save_settings(self.settings)
        self._refresh_scope_lists()

    def _refresh_scope_lists(self) -> None:
        if hasattr(self, "roots_list"):
            self.roots_list.delete(0, tk.END)
            for path in self.settings.get("roots", []):
                self.roots_list.insert(tk.END, path)
        if hasattr(self, "excludes_list"):
            self.excludes_list.delete(0, tk.END)
            for path in self.settings.get("excludes", []):
                self.excludes_list.insert(tk.END, path)

    def _import_data(self) -> None:
        path = filedialog.askopenfilename(title="导入 DATA", filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self._merge_imported_scopes(payload)
            self._merge_imported_tag_datasets(payload)
            count = self.store.import_data(Path(path))
            self.status_var.set(f"已导入 {count} 条 DATA。")
            self._refresh_current()
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))

    def _export_data(self) -> None:
        path = filedialog.asksaveasfilename(title="导出 DATA", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.store.export_data(Path(path))
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            payload["scope_presets"] = self._ensure_scope_presets()
            payload["tag_datasets"] = self.settings.get("tag_datasets", [])
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_var.set("DATA 已导出。")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _refresh_current(self) -> None:
        if self.current_activity == "manual":
            self._refresh_manual_browser()
        elif self.current_activity == "batch":
            self._show_batch_label()
        elif self.current_activity == "advanced":
            self._show_advanced_search()
        else:
            self._show_home()

    def _open_language_settings(self) -> None:
        win = tk.Toplevel(self)
        win.title("语言 / Language")
        win.geometry("520x320")
        win.resizable(False, False)
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=24, pady=22)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="语言 / Language", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(
            frame,
            text="选择正式软件界面语言。\nChoose the language used by the main app.",
            bg=SURFACE,
            fg=MUTED,
            justify=tk.LEFT,
            wraplength=440,
        ).pack(anchor=tk.W, pady=(4, 18))

        language_var = tk.StringVar(value=self.language if self.language in LANGUAGE_OPTIONS else "zh")
        for value, (primary, secondary) in LANGUAGE_OPTIONS.items():
            ttk.Radiobutton(frame, text=f"{primary} / {secondary}", variable=language_var, value=value).pack(anchor=tk.W, pady=6)

        note = (
            "提示：首次启动也会显示中英并列的语言选择窗口。\n"
            "Tip: the first launch also shows a bilingual language-choice window."
        )
        tk.Label(frame, text=note, bg=SURFACE, fg=MUTED, justify=tk.LEFT, wraplength=440).pack(anchor=tk.W, pady=(14, 0))

        buttons = tk.Frame(frame, bg=SURFACE)
        buttons.pack(fill=tk.X, pady=(18, 0))

        def save() -> None:
            self._set_language(language_var.get(), mark_selected=True)
            self.status_var.set("语言已保存 / Language saved.")
            win.destroy()

        tk.Button(buttons, text="保存 / Save", command=save, relief=tk.FLAT, bg=ACCENT, fg="white", padx=18, pady=8).pack(side=tk.RIGHT)
        tk.Button(buttons, text="取消 / Cancel", command=win.destroy, relief=tk.FLAT, bg="#eef3f8", padx=18, pady=8).pack(side=tk.RIGHT, padx=8)

    def _open_settings(self) -> None:
        self._open_automation_settings()

    def _open_automation_settings(self) -> None:
        win = tk.Toplevel(self)
        win.title("自动化配置")
        win.geometry("760x620")
        win.minsize(660, 500)
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=18, pady=18)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="自动化配置", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(frame, text="配置 OCR、AI 识图接口和强约束提示词。应用信息只在设置类窗口中显示。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(2, 14))

        enable_automation = tk.BooleanVar(value=bool(self.settings.get("enable_automation", True)))
        enable_ocr = tk.BooleanVar(value=bool(self.settings.get("enable_ocr", True)))
        enable_vision = tk.BooleanVar(value=bool(self.settings.get("enable_vision", False)))
        endpoint = tk.StringVar(value=self.settings.get("vision_endpoint", ""))
        model = tk.StringVar(value=self.settings.get("vision_model", ""))
        api_key = tk.StringVar(value=self.settings.get("vision_api_key", ""))

        for text, var in [
            ("启用自动化分析", enable_automation),
            ("启用 OCR", enable_ocr),
            ("启用识图大模型", enable_vision),
        ]:
            tk.Checkbutton(frame, text=text, variable=var, bg=SURFACE, fg=TEXT, selectcolor=SURFACE).pack(anchor=tk.W)

        form = tk.Frame(frame, bg=SURFACE)
        form.pack(fill=tk.X, pady=10)
        for row, (label, var, show) in enumerate([
            ("接口地址", endpoint, ""),
            ("模型名", model, ""),
            ("API Key", api_key, "*"),
        ]):
            tk.Label(form, text=label, bg=SURFACE, fg=MUTED).grid(row=row, column=0, sticky=tk.W, pady=5)
            tk.Entry(form, textvariable=var, show=show, relief=tk.FLAT, bg="#f8fafc").grid(row=row, column=1, sticky=tk.EW, padx=8, pady=5, ipady=5)
        form.columnconfigure(1, weight=1)

        tk.Label(frame, text="识图提示词", bg=SURFACE, fg=MUTED).pack(anchor=tk.W)
        prompt_text = tk.Text(frame, height=9, wrap=tk.WORD, relief=tk.FLAT, bg="#f8fafc")
        prompt_text.pack(fill=tk.BOTH, expand=True)
        prompt_text.insert("1.0", self.settings.get("vision_prompt", ""))

        buttons = tk.Frame(frame, bg=SURFACE)
        buttons.pack(fill=tk.X, pady=(12, 0))

        def save() -> None:
            self.settings.update(
                {
                    "enable_automation": enable_automation.get(),
                    "enable_ocr": enable_ocr.get(),
                    "enable_vision": enable_vision.get(),
                    "vision_endpoint": endpoint.get().strip(),
                    "vision_model": model.get().strip(),
                    "vision_api_key": api_key.get().strip(),
                    "vision_prompt": prompt_text.get("1.0", tk.END).strip(),
                }
            )
            save_settings(self.settings)
            win.destroy()
            self.status_var.set("设置已保存。")

        tk.Button(buttons, text="保存", command=save, relief=tk.FLAT, bg=ACCENT, fg="white", padx=18, pady=8).pack(side=tk.RIGHT)
        tk.Button(buttons, text="取消", command=win.destroy, relief=tk.FLAT, bg="#eef3f8", padx=18, pady=8).pack(side=tk.RIGHT, padx=8)

    def _open_data_management(self) -> None:
        win = tk.Toplevel(self)
        win.title("数据管理")
        win.geometry("720x460")
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=18, pady=18)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text="数据管理", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(frame, text="DATA、标签数据和检索范围数据都从设置中进出，不再散落在主界面。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(2, 16))

        grid = tk.Frame(frame, bg=SURFACE)
        grid.pack(fill=tk.BOTH, expand=True)
        cards = [
            ("完整 DATA", "保存或导入完整图片索引、四类记忆和隐藏标签状态。", [("导出完整 DATA", self._export_data), ("导入完整 DATA", self._import_data)]),
            ("标签数据", "只处理图片路径对应的文字、物体、结构、意义和状态。", [("导出标签数据", self._export_tag_data), ("导入标签数据", self._import_tag_data), ("标签数据集管理", self._open_tag_dataset_manager)]),
            ("检索范围", "黑白名单预设在检索范围窗口中导入导出。", [("打开检索范围", self._open_scope_manager), ("打开 DATA 目录", self._open_data_dir)]),
        ]
        for col, (title, desc, actions) in enumerate(cards):
            card = tk.Frame(grid, bg="#f8fafc", highlightbackground=LINE, highlightthickness=1, padx=14, pady=14)
            card.grid(row=0, column=col, sticky=tk.NSEW, padx=8)
            tk.Label(card, text=title, bg="#f8fafc", fg=TEXT, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor=tk.W)
            tk.Label(card, text=desc, bg="#f8fafc", fg=MUTED, wraplength=190, justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 12))
            for label, command in actions:
                tk.Button(card, text=label, command=command, relief=tk.FLAT, bg=ACCENT if "导出" in label or "打开检索" in label else "#eef3f8", fg="white" if "导出" in label or "打开检索" in label else TEXT, padx=12, pady=7).pack(fill=tk.X, pady=3)
        for col in range(3):
            grid.columnconfigure(col, weight=1)

    def _export_tag_data(self) -> None:
        path = filedialog.asksaveasfilename(title="导出标签数据", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        fields = ["path", "file_name", "file_hash", "image_text", "image_objects", "image_structure", "image_meaning", "custom_notes", "ocr_tagged", "ai_tagged", "manual_tagged"]
        payload = {
            "version": 1,
            "kind": "tag_data",
            "dataset": {
                "name": "标签数据 " + time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "scope_presets": self._ensure_scope_presets(),
            "images": [{field: row.get(field) for field in fields} for row in self.store.list_all()],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set("标签数据已导出。")

    def _import_tag_data(self) -> None:
        path = filedialog.askopenfilename(title="导入标签数据", filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self._merge_imported_scopes(payload)
        images = payload.get("images", [])
        count = 0
        for item in images:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            existing = self.store.get_by_path(item["path"])
            if existing:
                image_id = int(existing["id"])
            else:
                image_id = self.store.upsert_file(
                    {
                        "path": item["path"],
                        "file_name": item.get("file_name") or Path(item["path"]).name,
                        "file_hash": item.get("file_hash"),
                        "size_bytes": None,
                        "mtime": None,
                        "width": None,
                        "height": None,
                    }
                )
            self.store.update_metadata(
                image_id,
                {
                    "image_text": item.get("image_text", ""),
                    "image_objects": item.get("image_objects", ""),
                    "image_structure": item.get("image_structure", ""),
                    "image_meaning": item.get("image_meaning", ""),
                    "custom_notes": item.get("custom_notes", ""),
                    "ocr_tagged": int(bool(item.get("ocr_tagged", 0))),
                    "ai_tagged": int(bool(item.get("ai_tagged", 0))),
                    "manual_tagged": int(bool(item.get("manual_tagged", 0))),
                },
            )
            count += 1
        self.status_var.set(f"已导入 {count} 条标签数据。")
        dataset = payload.get("dataset") if isinstance(payload.get("dataset"), dict) else {}
        self._register_tag_dataset(dataset.get("name") or Path(path).stem, count, payload.get("scope_presets", []))
        self._refresh_current()

    def _merge_imported_scopes(self, payload: Dict[str, Any]) -> None:
        incoming = payload.get("scope_presets", [])
        if not isinstance(incoming, list) or not incoming:
            return
        presets = self._ensure_scope_presets()
        existing_names = {str(preset.get("name")) for preset in presets}
        for preset in incoming:
            if not isinstance(preset, dict):
                continue
            name = str(preset.get("name") or "导入范围")
            if name in existing_names:
                name = name + "（导入）"
            copied = dict(preset)
            copied["name"] = name
            copied["directories"] = [
                self._normalize_directory_entry(entry)
                for entry in copied.get("directories", [])
            ]
            presets.append(copied)
            existing_names.add(name)
        self.settings["scope_presets"] = presets
        save_settings(self.settings)

    def _merge_imported_tag_datasets(self, payload: Dict[str, Any]) -> None:
        incoming = payload.get("tag_datasets", [])
        if not isinstance(incoming, list) or not incoming:
            return
        datasets = list(self.settings.get("tag_datasets") or [])
        datasets.extend(item for item in incoming if isinstance(item, dict))
        self.settings["tag_datasets"] = datasets
        save_settings(self.settings)

    def _ensure_tag_datasets(self) -> List[Dict[str, Any]]:
        datasets = list(self.settings.get("tag_datasets") or [])
        if not datasets:
            datasets = [
                {
                    "id": "default",
                    "name": "默认数据集",
                    "image_count": 0,
                    "scope_preset_names": [],
                    "created_at": "",
                }
            ]
            self.settings["tag_datasets"] = datasets
            save_settings(self.settings)
        return datasets

    def _register_tag_dataset(self, name: str, count: int, scope_presets: Any) -> None:
        if not isinstance(scope_presets, list):
            scope_presets = []
        scope_names = [str(preset.get("name")) for preset in scope_presets if isinstance(preset, dict) and preset.get("name")]
        datasets = list(self.settings.get("tag_datasets") or [])
        datasets.append(
            {
                "id": str(int(time.time() * 1000)),
                "name": name,
                "image_count": count,
                "scope_preset_names": scope_names,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self.settings["tag_datasets"] = datasets
        save_settings(self.settings)

    def _open_tag_dataset_manager(self) -> None:
        win = tk.Toplevel(self)
        win.title("标签数据集管理")
        win.geometry("1260x680")
        win.minsize(1120, 560)
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=18, pady=18)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text="标签数据集管理", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(frame, text="一个标签数据集可以关联多个检索范围预设；这里可以查看双向关联。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(2, 12))

        body = tk.Frame(frame, bg=SURFACE)
        body.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(body, bg=SURFACE)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 14))
        right = tk.Frame(body, bg=SURFACE, width=440)
        right.pack(side=tk.LEFT, fill=tk.BOTH)
        right.pack_propagate(False)

        tk.Label(left, text="标签数据集", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        dataset_tree = ttk.Treeview(left, columns=("count", "scopes", "created"), show="tree headings")
        dataset_tree.heading("#0", text="名称")
        dataset_tree.heading("count", text="图片数")
        dataset_tree.heading("scopes", text="关联范围")
        dataset_tree.heading("created", text="创建/导入时间")
        dataset_tree.column("#0", width=240)
        dataset_tree.column("count", width=70, anchor=tk.CENTER)
        dataset_tree.column("scopes", width=300)
        dataset_tree.column("created", width=180)
        dataset_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        tk.Label(right, text="检索范围关联的标签数据", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        scope_tree = ttk.Treeview(right, columns=("datasets",), show="tree headings")
        scope_tree.heading("#0", text="检索范围预设")
        scope_tree.heading("datasets", text="关联标签数据集")
        scope_tree.column("#0", width=180)
        scope_tree.column("datasets", width=250)
        scope_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        def refresh_trees() -> None:
            dataset_tree.delete(*dataset_tree.get_children())
            scope_tree.delete(*scope_tree.get_children())
            datasets = self._ensure_tag_datasets()
            for index, dataset in enumerate(datasets):
                scopes = "、".join(dataset.get("scope_preset_names") or [])
                dataset_tree.insert("", tk.END, iid=str(index), text=dataset.get("name") or "未命名标签数据", values=(dataset.get("image_count", 0), scopes, dataset.get("created_at", "")))

            scope_names = [preset.get("name") or "未命名范围" for preset in self._ensure_scope_presets()]
            for scope_name in scope_names:
                linked = [dataset.get("name") or "未命名标签数据" for dataset in datasets if scope_name in (dataset.get("scope_preset_names") or [])]
                scope_tree.insert("", tk.END, text=scope_name, values=("、".join(linked) if linked else "无",))

        def new_dataset() -> None:
            name = simpledialog.askstring("新建数据集", "请输入数据集名称：", parent=win)
            if not name:
                return
            datasets = self._ensure_tag_datasets()
            datasets.append(
                {
                    "id": str(int(time.time() * 1000)),
                    "name": name.strip(),
                    "image_count": 0,
                    "scope_preset_names": [],
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            self.settings["tag_datasets"] = datasets
            save_settings(self.settings)
            refresh_trees()

        def delete_dataset() -> None:
            selection = dataset_tree.selection()
            if not selection:
                messagebox.showinfo("未选择数据集", "请先选择一个数据集。")
                return
            index = int(selection[0])
            datasets = self._ensure_tag_datasets()
            if index >= len(datasets):
                return
            if datasets[index].get("id") == "default" and len(datasets) == 1:
                messagebox.showinfo("保留默认数据集", "至少需要保留一个数据集。")
                return
            if messagebox.askyesno("删除数据集", "确定删除这个数据集记录吗？这不会删除图片文件。"):
                del datasets[index]
                if not datasets:
                    datasets = []
                self.settings["tag_datasets"] = datasets
                save_settings(self.settings)
                self._ensure_tag_datasets()
                refresh_trees()

        refresh_trees()

        buttons = tk.Frame(frame, bg=SURFACE)
        buttons.pack(fill=tk.X, pady=(12, 0))
        tk.Button(buttons, text="新建数据集", command=new_dataset, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="删除选中数据集", command=delete_dataset, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="导入标签数据", command=self._import_tag_data, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="导出当前标签数据", command=self._export_tag_data, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)

    def _entry_path_and_recursive(self, entry: Any) -> tuple[str, bool]:
        if isinstance(entry, dict):
            return str(entry.get("path") or ""), bool(entry.get("include_subdirs", True))
        return str(entry or ""), True

    def _normalize_directory_entry(self, entry: Any, default_recursive: bool = True) -> Dict[str, Any]:
        if isinstance(entry, dict):
            return {
                "path": str(entry.get("path") or ""),
                "include_subdirs": bool(entry.get("include_subdirs", default_recursive)),
            }
        return {"path": str(entry or ""), "include_subdirs": bool(default_recursive)}

    def _preset_directory_entries(self, preset: Dict[str, Any]) -> List[Dict[str, Any]]:
        default_recursive = bool(preset.get("include_subdirs", True))
        entries = [
            self._normalize_directory_entry(entry, default_recursive)
            for entry in preset.get("directories", [])
        ]
        return [entry for entry in entries if entry.get("path")]

    def _recursive_summary(self, entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return "-"
        values = {bool(entry.get("include_subdirs", True)) for entry in entries}
        if values == {True}:
            return "全部"
        if values == {False}:
            return "无"
        return "混合"

    def _ensure_scope_presets(self) -> List[Dict[str, Any]]:
        presets = list(self.settings.get("scope_presets") or [])
        if not presets:
            presets = [
                {"name": "默认白名单", "kind": "whitelist", "include_subdirs": True, "directories": []},
                {"name": "默认黑名单", "kind": "blacklist", "include_subdirs": True, "directories": []},
            ]
        if self.settings.get("roots") and not any(p.get("kind") == "whitelist" and p.get("directories") for p in presets):
            roots = [self._normalize_directory_entry(entry) for entry in self.settings.get("roots", [])]
            presets[0]["directories"] = [entry for entry in roots if entry.get("path")]
        blacklist = next((p for p in presets if p.get("kind") == "blacklist"), None)
        if blacklist and self.settings.get("excludes") and not blacklist.get("directories"):
            excludes = [self._normalize_directory_entry(entry) for entry in self.settings.get("excludes", [])]
            blacklist["directories"] = [entry for entry in excludes if entry.get("path")]
        for preset in presets:
            preset.setdefault("active", True)
        self.settings["scope_presets"] = presets
        save_settings(self.settings)
        return presets

    def _open_scope_manager(self) -> None:
        win = tk.Toplevel(self)
        win.title("检索范围")
        win.geometry("920x560")
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=18, pady=18)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text="检索范围", bg=SURFACE, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor=tk.W)
        tk.Label(frame, text="勾选左侧启用框后，点击“应用”即可让对应白名单/黑名单参与当前检索范围。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(2, 12))

        body = tk.Frame(frame, bg=SURFACE)
        body.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(body, columns=("active", "name", "kind", "recursive", "count"), show="headings", height=12)
        tree.heading("active", text="启用")
        tree.heading("name", text="预设")
        tree.heading("kind", text="类型")
        tree.heading("recursive", text="包含子目录")
        tree.heading("count", text="目录数")
        tree.column("active", width=60, anchor=tk.CENTER)
        tree.column("name", width=300)
        tree.column("kind", width=120, anchor=tk.CENTER)
        tree.column("recursive", width=120, anchor=tk.CENTER)
        tree.column("count", width=80, anchor=tk.CENTER)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=tree.yview)
        scroll.pack(side=tk.LEFT, fill=tk.Y)
        tree.configure(yscrollcommand=scroll.set)

        buttons = tk.Frame(body, bg=SURFACE, padx=12)
        buttons.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_tree() -> None:
            tree.delete(*tree.get_children())
            for index, preset in enumerate(self._ensure_scope_presets()):
                active = "☑" if preset.get("active", True) else "☐"
                kind = "白名单" if preset.get("kind") == "whitelist" else "黑名单"
                entries = self._preset_directory_entries(preset)
                recursive = self._recursive_summary(entries)
                count = len(entries)
                tree.insert("", tk.END, iid=str(index), values=(active, preset.get("name") or f"预设 {index + 1}", kind, recursive, count))

        def selected_index() -> Optional[int]:
            selection = tree.selection()
            if not selection:
                return None
            return int(selection[0])

        apply_button: Dict[str, tk.Button] = {}

        def mark_apply_dirty() -> None:
            if "button" in apply_button:
                apply_button["button"].configure(bg="#dff0ff")

        def edit_selected() -> None:
            index = selected_index()
            if index is None:
                messagebox.showinfo("未选择预设", "请先选择一个预设。")
                return
            self._edit_scope_preset(index, lambda: (refresh_tree(), mark_apply_dirty()))

        def new_preset() -> None:
            self._edit_scope_preset(None, lambda: (refresh_tree(), mark_apply_dirty()))

        def delete_selected() -> None:
            index = selected_index()
            if index is None:
                return
            presets = self._ensure_scope_presets()
            if messagebox.askyesno("删除预设", "确定删除这个检索范围预设吗？"):
                del presets[index]
                self.settings["scope_presets"] = presets
                save_settings(self.settings)
                refresh_tree()
                mark_apply_dirty()

        def apply_active_presets() -> None:
            roots: List[Dict[str, Any]] = []
            excludes: List[Dict[str, Any]] = []
            for preset in self._ensure_scope_presets():
                if not preset.get("active", True):
                    continue
                entries = self._preset_directory_entries(preset)
                if preset.get("kind") == "whitelist":
                    roots.extend(entries)
                else:
                    excludes.extend(entries)
            self.settings["roots"] = roots
            self.settings["excludes"] = excludes
            save_settings(self.settings)
            self.status_var.set("启用的检索范围名单已应用。")
            if "button" in apply_button:
                apply_button["button"].configure(bg="#eef3f8")
            self._refresh_current()

        def toggle_active(event: Any) -> None:
            if tree.identify_column(event.x) != "#1":
                return
            item_id = tree.identify_row(event.y)
            if not item_id:
                return
            presets = self._ensure_scope_presets()
            index = int(item_id)
            presets[index]["active"] = not bool(presets[index].get("active", True))
            self.settings["scope_presets"] = presets
            save_settings(self.settings)
            refresh_tree()
            mark_apply_dirty()

        for label, command in [
            ("新建名单", new_preset),
            ("编辑", edit_selected),
            ("删除", delete_selected),
            ("导入范围数据", self._import_scope_presets),
            ("导出范围数据", self._export_scope_presets),
            ("刷新", refresh_tree),
            ("重新扫描", self._rescan_library),
        ]:
            color = "#eef3f8"
            fg = TEXT
            tk.Button(buttons, text=label, command=command, relief=tk.FLAT, bg=color, fg=fg, padx=12, pady=8).pack(fill=tk.X, pady=4)

        apply_button["button"] = tk.Button(buttons, text="应用", command=apply_active_presets, relief=tk.FLAT, bg="#eef3f8", fg=TEXT, padx=12, pady=8)
        apply_button["button"].pack(fill=tk.X, pady=(14, 4))

        tree.bind("<Button-1>", toggle_active, add="+")
        tree.bind("<Double-1>", lambda _event: edit_selected())
        bind_mousewheel(tree, tree)
        refresh_tree()

    def _edit_scope_preset(self, index: Optional[int], on_saved: Callable[[], None], kind: str = "whitelist") -> None:
        presets = self._ensure_scope_presets()
        if index is None:
            preset = {"name": "新名单", "kind": kind, "include_subdirs": True, "directories": [], "active": True}
        else:
            preset = dict(presets[index])
            preset["directories"] = list(preset.get("directories") or [])

        win = tk.Toplevel(self)
        win.title("编辑检索范围预设")
        win.geometry("680x500")
        win.transient(self)
        frame = tk.Frame(win, bg=SURFACE, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)
        name_var = tk.StringVar(value=preset.get("name", ""))
        kind_var = tk.StringVar(value="白名单" if preset.get("kind") == "whitelist" else "黑名单")

        form = tk.Frame(frame, bg=SURFACE)
        form.pack(fill=tk.X)
        tk.Label(form, text="名称", bg=SURFACE, fg=MUTED).grid(row=0, column=0, sticky=tk.W, pady=5)
        tk.Entry(form, textvariable=name_var, relief=tk.FLAT, bg="#f8fafc").grid(row=0, column=1, sticky=tk.EW, padx=8, pady=5, ipady=5)
        tk.Label(form, text="类型", bg=SURFACE, fg=MUTED).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Combobox(form, textvariable=kind_var, values=["白名单", "黑名单"], state="readonly").grid(row=1, column=1, sticky=tk.W, padx=8, pady=5)
        form.columnconfigure(1, weight=1)

        tk.Label(frame, text="目录列表。每个目录后面的勾表示是否包含子目录。", bg=SURFACE, fg=MUTED).pack(anchor=tk.W, pady=(12, 4))
        dir_tree = ttk.Treeview(frame, columns=("recursive",), show="tree headings", height=10)
        dir_tree.heading("#0", text="目录")
        dir_tree.heading("recursive", text="包含子目录")
        dir_tree.column("#0", width=500)
        dir_tree.column("recursive", width=110, anchor=tk.CENTER)
        dir_tree.pack(fill=tk.BOTH, expand=True)
        for entry in self._preset_directory_entries(preset):
            mark = "☑" if entry.get("include_subdirs", True) else "☐"
            dir_tree.insert("", tk.END, text=entry.get("path", ""), values=(mark,))

        row = tk.Frame(frame, bg=SURFACE)
        row.pack(fill=tk.X, pady=10)
        edit_mode = {"enabled": False}

        def add_dir() -> None:
            path = filedialog.askdirectory(title="添加目录")
            if path:
                dir_tree.insert("", tk.END, text=path, values=("☑",))

        def remove_dir() -> None:
            for selected in dir_tree.selection():
                dir_tree.delete(selected)

        def toggle_selected_recursive(_event: Any = None) -> None:
            if not edit_mode["enabled"]:
                return
            selected = dir_tree.selection()
            if not selected:
                return
            item_id = selected[0]
            current = dir_tree.item(item_id, "values")[0]
            next_value = "☐" if current == "☑" else "☑"
            dir_tree.item(item_id, values=(next_value,))

        def toggle_edit_mode() -> None:
            edit_mode["enabled"] = not edit_mode["enabled"]
            edit_button.configure(text="确认" if edit_mode["enabled"] else "编辑包含子目录")
            self.status_var.set("双击目录行可切换包含子目录。" if edit_mode["enabled"] else "目录递归选项已确认。")

        def save() -> None:
            directories = []
            for item_id in dir_tree.get_children():
                values = dir_tree.item(item_id, "values")
                directories.append(
                    {
                        "path": dir_tree.item(item_id, "text"),
                        "include_subdirs": bool(values and values[0] == "☑"),
                    }
                )
            new_preset = {
                "name": name_var.get().strip() or "未命名预设",
                "kind": "whitelist" if kind_var.get() == "白名单" else "blacklist",
                "directories": directories,
                "active": bool(preset.get("active", True)),
            }
            if index is None:
                presets.append(new_preset)
            else:
                presets[index] = new_preset
            self.settings["scope_presets"] = presets
            save_settings(self.settings)
            on_saved()
            win.destroy()

        tk.Button(row, text="添加目录", command=add_dir, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        tk.Button(row, text="删除选中", command=remove_dir, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8).pack(side=tk.LEFT, padx=4)
        edit_button = tk.Button(row, text="编辑包含子目录", command=toggle_edit_mode, relief=tk.FLAT, bg="#eef3f8", padx=12, pady=8)
        edit_button.pack(side=tk.LEFT, padx=4)
        tk.Button(row, text="保存", command=save, relief=tk.FLAT, bg=ACCENT, fg="white", padx=16, pady=8).pack(side=tk.RIGHT, padx=4)
        dir_tree.bind("<Double-1>", toggle_selected_recursive)

    def _export_scope_presets(self) -> None:
        path = filedialog.asksaveasfilename(title="导出检索范围数据", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        payload = {
            "version": 1,
            "kind": "scope_presets",
            "scope_presets": self._ensure_scope_presets(),
            "roots": self.settings.get("roots", []),
            "excludes": self.settings.get("excludes", []),
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set("检索范围数据已导出。")

    def _import_scope_presets(self) -> None:
        path = filedialog.askopenfilename(title="导入检索范围数据", filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        incoming = payload.get("scope_presets", [])
        if not isinstance(incoming, list):
            raise ValueError("检索范围数据格式不正确")
        presets = self._ensure_scope_presets()
        presets.extend(incoming)
        self.settings["scope_presets"] = presets
        if "roots" in payload:
            self.settings["roots"] = payload["roots"]
        if "excludes" in payload:
            self.settings["excludes"] = payload["excludes"]
        save_settings(self.settings)
        self.status_var.set("检索范围数据已导入。")

    def _rescan_library(self) -> None:
        if messagebox.askyesno("重新扫描", "重新扫描会重新读取所有目录并重建自动识别缓存，可能很漫长。它不会删除图片文件，也不会删除已有人工标签。是否继续？"):
            self._start_indexing(force_rebuild=True)

    def _show_about(self) -> None:
        messagebox.showinfo(APP_TITLE, "梗图搜查器\n本地 DATA、OCR、AI 识图、批量标签和手动标签。")

    def _open_data_dir(self) -> None:
        os.startfile(str(data_dir()))

    def _open_app_dir(self) -> None:
        os.startfile(str(Path(__file__).resolve().parent.parent))

    def _open_readme(self) -> None:
        path = Path(__file__).resolve().parent.parent / "README.md"
        if path.exists():
            os.startfile(str(path))


def main() -> None:
    app = MemeFinderApp()
    app.mainloop()
