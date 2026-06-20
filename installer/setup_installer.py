from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_ID = "MemeFinder"
APP_TITLE = "梗图搜查器"
SETUP_TITLE = f"{APP_TITLE} Setup"
PAYLOAD_NAME = "app_payload.zip"
VERSION = "0.1.0"
TAG_EDITOR_EXE = "TagDataEditor.exe"
TAG_EDITOR_TITLE = "Tag Data Editor - Experimental"
LANGUAGE_CHOICES = {"中文": "zh", "English": "en"}

SETUP_TEXT = {
    "zh": {
        "setup_title": f"{APP_TITLE} Setup",
        "subtitle": "安装应用、创建快捷方式，并选择普通或便携数据模式。",
        "cancel": "取消",
        "next": "下一步",
        "back": "上一步",
        "install": "安装",
        "installing_button": "安装中",
        "finish": "完成",
        "welcome_title": "欢迎使用梗图搜查器安装向导",
        "welcome_body": (
            "这个 Setup 会安装当前构建好的 MemeFinder 应用目录。\n\n"
            "安装过程中不会自动扫描图片、不会联网，也不会删除已有数据。"
            "如果安装到已有目录，会覆盖程序文件，但保留数据目录。"
        ),
        "target_title": "安装位置与数据模式",
        "target_desc": "普通模式会把配置和缓存放到用户数据目录；便携模式会在安装目录内保存 data。",
        "mode_normal": "普通安装模式（推荐）",
        "mode_portable": "便携模式（在安装目录内保存 data）",
        "install_to": "安装到：",
        "browse": "浏览",
        "components_title": "可选组件",
        "components_desc": "选择要额外安装的实验功能。未勾选时，安装器会从目标目录中移除对应工具。",
        "tag_editor_component": "批量标签数据编辑器（Experimental）",
        "tag_editor_desc": (
            "用于批量编辑导出的标签数据 JSON：路径前缀迁移、文本查找替换、图片意义标签批量添加/删除、"
            "删除不存在文件记录。默认不安装。"
        ),
        "shortcuts_title": "快捷方式",
        "shortcuts_desc": "选择要创建的位置。开始菜单快捷方式会包含已勾选的实验工具。",
        "desktop_shortcut": "创建桌面快捷方式",
        "start_menu_shortcut": "创建开始菜单快捷方式",
        "summary_title": "准备安装",
        "summary_app": "应用",
        "summary_version": "版本",
        "summary_location": "位置",
        "summary_mode": "模式",
        "summary_shortcuts": "快捷方式",
        "summary_components": "组件",
        "shortcut_desktop": "桌面",
        "shortcut_start_menu": "开始菜单",
        "shortcut_none": "不创建快捷方式",
        "component_main": "主程序",
        "component_tag_editor": "实验性批量标签数据编辑器",
        "installing_title": "正在安装",
        "done_title": "安装完成",
        "done_body": f"{APP_TITLE} 已安装到：\n{{path}}",
        "launch_after": "完成后启动梗图搜查器",
        "choose_target": "选择安装目录",
        "target_required": "请选择安装目录。",
        "confirm_cancel": "确定要退出安装器吗？",
        "install_failed": "安装失败：\n{error}",
        "progress_create_dir": "正在创建安装目录",
        "progress_copy": "正在复制应用文件 {index}/{total}",
        "progress_portable": "正在启用便携模式",
        "progress_normal": "正在启用普通安装模式",
        "progress_tag_editor": "正在安装实验性标签数据编辑器",
        "progress_remove_tag_editor": "正在移除未选择的实验工具",
        "progress_desktop_shortcut": "正在创建桌面快捷方式",
        "progress_start_menu_shortcut": "正在创建开始菜单快捷方式",
        "progress_done": "安装完成",
        "unsafe_path": "安装包里包含不安全路径: {member}",
        "missing_payload": "找不到安装资源: {path}",
        "missing_tag_editor": "安装资源中缺少实验工具: {path}",
    },
    "en": {
        "setup_title": "MemeFinder Setup",
        "subtitle": "Install the app, create shortcuts, and choose normal or portable data mode.",
        "cancel": "Cancel",
        "next": "Next",
        "back": "Back",
        "install": "Install",
        "installing_button": "Installing",
        "finish": "Finish",
        "welcome_title": "Welcome to MemeFinder Setup",
        "welcome_body": (
            "This setup installs the currently built MemeFinder application folder.\n\n"
            "It will not scan images, connect to the network, or delete existing data during installation. "
            "If you install into an existing folder, program files are overwritten while the data folder is kept."
        ),
        "target_title": "Install Location and Data Mode",
        "target_desc": "Normal mode stores settings and cache in the user data folder. Portable mode keeps data inside the install folder.",
        "mode_normal": "Normal install mode (recommended)",
        "mode_portable": "Portable mode (keep data inside the install folder)",
        "install_to": "Install to:",
        "browse": "Browse",
        "components_title": "Optional Components",
        "components_desc": "Choose extra experimental features. If unchecked, setup removes that tool from the target folder.",
        "tag_editor_component": "Tag Data Editor (Experimental)",
        "tag_editor_desc": (
            "Batch edit exported tag-data JSON files: path-prefix migration, text find/replace, image-meaning tag add/remove, "
            "and removal of missing-file records. Not installed by default."
        ),
        "shortcuts_title": "Shortcuts",
        "shortcuts_desc": "Choose where shortcuts should be created. Start Menu shortcuts include selected experimental tools.",
        "desktop_shortcut": "Create Desktop shortcut",
        "start_menu_shortcut": "Create Start Menu shortcuts",
        "summary_title": "Ready to Install",
        "summary_app": "App",
        "summary_version": "Version",
        "summary_location": "Location",
        "summary_mode": "Mode",
        "summary_shortcuts": "Shortcuts",
        "summary_components": "Components",
        "shortcut_desktop": "Desktop",
        "shortcut_start_menu": "Start Menu",
        "shortcut_none": "No shortcuts",
        "component_main": "Main app",
        "component_tag_editor": "Experimental Tag Data Editor",
        "installing_title": "Installing",
        "done_title": "Installation Complete",
        "done_body": "MemeFinder has been installed to:\n{path}",
        "launch_after": "Launch MemeFinder when setup closes",
        "choose_target": "Choose install folder",
        "target_required": "Please choose an install folder.",
        "confirm_cancel": "Exit setup?",
        "install_failed": "Installation failed:\n{error}",
        "progress_create_dir": "Creating install folder",
        "progress_copy": "Copying application files {index}/{total}",
        "progress_portable": "Enabling portable mode",
        "progress_normal": "Enabling normal install mode",
        "progress_tag_editor": "Installing experimental Tag Data Editor",
        "progress_remove_tag_editor": "Removing unchecked experimental tool",
        "progress_desktop_shortcut": "Creating Desktop shortcut",
        "progress_start_menu_shortcut": "Creating Start Menu shortcuts",
        "progress_done": "Installation complete",
        "unsafe_path": "Setup package contains an unsafe path: {member}",
        "missing_payload": "Setup payload was not found: {path}",
        "missing_tag_editor": "Experimental tool is missing from payload: {path}",
    },
}


def setup_text(language: str, key: str, **kwargs: object) -> str:
    table = SETUP_TEXT.get(language, SETUP_TEXT["zh"])
    value = table.get(key, SETUP_TEXT["zh"].get(key, key))
    return value.format(**kwargs) if kwargs else value


def resource_path(relative_path: str | Path) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = Path(__file__).resolve().parent
    return base / Path(relative_path)


def default_install_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "Programs" / APP_ID
    return Path.home() / "AppData" / "Local" / "Programs" / APP_ID


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def create_shortcut(shortcut_path: Path, target_path: Path, working_dir: Path) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut({ps_quote(shortcut_path)})
$shortcut.TargetPath = {ps_quote(target_path)}
$shortcut.WorkingDirectory = {ps_quote(working_dir)}
$shortcut.IconLocation = {ps_quote(str(target_path) + ",0")}
$shortcut.Save()
"""
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creation_flags,
    )


def desktop_shortcut_path() -> Path:
    return Path.home() / "Desktop" / f"{APP_TITLE}.lnk"


def start_menu_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / "AppData" / "Roaming"
    return root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_ID / f"{APP_TITLE}.lnk"


def tag_editor_start_menu_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / "AppData" / "Roaming"
    return root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_ID / f"{TAG_EDITOR_TITLE}.lnk"


def uninstall_start_menu_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / "AppData" / "Roaming"
    return root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_ID / "UNINSTALL.lnk"


def remove_file_if_exists(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def extract_payload(payload_zip: Path, target_dir: Path, progress: callable | None = None, language: str = "zh") -> None:
    target_root = target_dir.resolve()
    with zipfile.ZipFile(payload_zip, "r") as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        total = max(1, len(members))
        for index, member in enumerate(members, 1):
            destination = (target_root / member.filename).resolve()
            if destination != target_root and target_root not in destination.parents:
                raise ValueError(setup_text(language, "unsafe_path", member=member.filename))
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, destination.open("wb") as output:
                output.write(source.read())
            if progress:
                progress(setup_text(language, "progress_copy", index=index, total=total))


def install_application(
    target_dir: Path,
    mode: str,
    make_desktop_shortcut: bool,
    make_start_menu_shortcut: bool,
    include_tag_editor: bool = False,
    language: str = "zh",
    progress: callable | None = None,
) -> Path:
    target_dir = target_dir.expanduser().resolve()
    payload_zip = resource_path(PAYLOAD_NAME)
    if not payload_zip.exists():
        raise FileNotFoundError(setup_text(language, "missing_payload", path=payload_zip))

    if progress:
        progress(setup_text(language, "progress_create_dir"))
    target_dir.mkdir(parents=True, exist_ok=True)

    extract_payload(payload_zip, target_dir, progress, language)

    portable_marker = target_dir / "portable.mode"
    if mode == "portable":
        if progress:
            progress(setup_text(language, "progress_portable"))
        portable_marker.write_text("", encoding="utf-8")
        data_dir = target_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        if progress:
            progress(setup_text(language, "progress_normal"))
        if portable_marker.exists():
            portable_marker.unlink()

    tag_editor_path = target_dir / TAG_EDITOR_EXE
    tag_editor_shortcut = tag_editor_start_menu_shortcut_path()
    if include_tag_editor:
        if progress:
            progress(setup_text(language, "progress_tag_editor"))
        if not tag_editor_path.exists():
            raise FileNotFoundError(setup_text(language, "missing_tag_editor", path=tag_editor_path))
    else:
        if progress:
            progress(setup_text(language, "progress_remove_tag_editor"))
        remove_file_if_exists(tag_editor_path)
        remove_file_if_exists(tag_editor_shortcut)

    exe_path = target_dir / "MemeFinder.exe"
    uninstall_path = target_dir / "UNINSTALL.bat"
    uninstall_shortcut = uninstall_start_menu_shortcut_path()
    if make_desktop_shortcut:
        if progress:
            progress(setup_text(language, "progress_desktop_shortcut"))
        create_shortcut(desktop_shortcut_path(), exe_path, target_dir)
    if make_start_menu_shortcut:
        if progress:
            progress(setup_text(language, "progress_start_menu_shortcut"))
        create_shortcut(start_menu_shortcut_path(), exe_path, target_dir)
        if include_tag_editor:
            create_shortcut(tag_editor_shortcut, tag_editor_path, target_dir)
        if uninstall_path.exists():
            create_shortcut(uninstall_shortcut, uninstall_path, target_dir)
    else:
        remove_file_if_exists(uninstall_shortcut)

    if progress:
        progress(setup_text(language, "progress_done"))
    return target_dir


class SetupWizard(tk.Tk):
    PAGE_WELCOME = 0
    PAGE_TARGET = 1
    PAGE_COMPONENTS = 2
    PAGE_SHORTCUTS = 3
    PAGE_SUMMARY = 4
    PAGE_INSTALLING = 5
    PAGE_DONE = 6

    def __init__(self) -> None:
        super().__init__()
        self.geometry("720x540")
        self.minsize(680, 500)
        self.configure(bg="#f5f7fb")

        self.language_choice_var = tk.StringVar(value="中文")
        self.mode_var = tk.StringVar(value="normal")
        self.target_var = tk.StringVar(value=str(default_install_dir()))
        self.tag_editor_var = tk.BooleanVar(value=False)
        self.desktop_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="")
        self.install_queue: "queue.Queue[tuple[str, str | Path | Exception]]" = queue.Queue()
        self.installed_dir: Path | None = None
        self.page_index = self.PAGE_WELCOME
        self.installing = False
        self.logo_image: tk.PhotoImage | None = None

        self._apply_icon()
        self._build_layout()
        self._render_page()

    def language_code(self) -> str:
        return LANGUAGE_CHOICES.get(self.language_choice_var.get(), "zh")

    def tr(self, key: str, **kwargs: object) -> str:
        return setup_text(self.language_code(), key, **kwargs)

    def _apply_icon(self) -> None:
        try:
            png_path = resource_path(Path("assets") / "MemeFinder.png")
            ico_path = resource_path(Path("assets") / "MemeFinder.ico")
            if png_path.exists():
                image = tk.PhotoImage(file=str(png_path))
                shrink = max(1, image.width() // 96)
                self.logo_image = image.subsample(shrink, shrink)
                self.iconphoto(True, self.logo_image)
            if ico_path.exists():
                self.iconbitmap(str(ico_path))
        except tk.TclError:
            pass

    def _build_layout(self) -> None:
        self.header = tk.Frame(self, bg="#ffffff", height=84, highlightbackground="#dfe4ee", highlightthickness=1)
        self.header.pack(side=tk.TOP, fill=tk.X)
        title_wrap = tk.Frame(self.header, bg="#ffffff")
        title_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=24, pady=14)
        self.title_label = tk.Label(title_wrap, bg="#ffffff", fg="#1d2636", font=("Microsoft YaHei UI", 20, "bold"))
        self.title_label.pack(anchor=tk.W)
        self.subtitle_label = tk.Label(title_wrap, bg="#ffffff", fg="#687385", font=("Microsoft YaHei UI", 10))
        self.subtitle_label.pack(anchor=tk.W)

        language_box = ttk.Combobox(
            self.header,
            textvariable=self.language_choice_var,
            values=list(LANGUAGE_CHOICES.keys()),
            state="readonly",
            width=10,
        )
        language_box.pack(side=tk.RIGHT, padx=22, pady=20)
        self.language_choice_var.trace_add("write", lambda *_args: self._render_page())

        self.body = tk.Frame(self, bg="#f5f7fb")
        self.body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=28, pady=22)

        self.footer = tk.Frame(self, bg="#ffffff", height=64, highlightbackground="#dfe4ee", highlightthickness=1)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        self.cancel_button = ttk.Button(self.footer, command=self._cancel)
        self.cancel_button.pack(side=tk.RIGHT, padx=(8, 22), pady=16)
        self.next_button = ttk.Button(self.footer, command=self._next)
        self.next_button.pack(side=tk.RIGHT, padx=8, pady=16)
        self.back_button = ttk.Button(self.footer, command=self._back)
        self.back_button.pack(side=tk.RIGHT, padx=8, pady=16)

    def _clear_body(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _render_page(self) -> None:
        self.title(self.tr("setup_title"))
        self.title_label.configure(text=self.tr("setup_title"))
        self.subtitle_label.configure(text=self.tr("subtitle"))
        self._clear_body()
        pages = [
            self._page_welcome,
            self._page_target,
            self._page_components,
            self._page_shortcuts,
            self._page_summary,
            self._page_installing,
            self._page_done,
        ]
        pages[self.page_index]()
        self.back_button.configure(state=tk.NORMAL if self.page_index not in (self.PAGE_WELCOME, self.PAGE_INSTALLING, self.PAGE_DONE) else tk.DISABLED)
        self.cancel_button.configure(text=self.tr("cancel"), state=tk.DISABLED if self.page_index == self.PAGE_INSTALLING else tk.NORMAL)
        self.back_button.configure(text=self.tr("back"))
        if self.page_index == self.PAGE_SUMMARY:
            self.next_button.configure(text=self.tr("install"), state=tk.NORMAL)
        elif self.page_index == self.PAGE_INSTALLING:
            self.next_button.configure(text=self.tr("installing_button"), state=tk.DISABLED)
        elif self.page_index == self.PAGE_DONE:
            self.next_button.configure(text=self.tr("finish"), state=tk.NORMAL)
        else:
            self.next_button.configure(text=self.tr("next"), state=tk.NORMAL)

    def _page_welcome(self) -> None:
        if self.logo_image:
            tk.Label(self.body, image=self.logo_image, bg="#f5f7fb").pack(anchor=tk.W, pady=(0, 14))
        tk.Label(self.body, text=self.tr("welcome_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor=tk.W)
        tk.Label(self.body, text=self.tr("welcome_body"), bg="#f5f7fb", fg="#3d4654", justify=tk.LEFT, wraplength=620, font=("Microsoft YaHei UI", 11)).pack(anchor=tk.W, pady=18)

    def _page_target(self) -> None:
        tk.Label(self.body, text=self.tr("target_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        tk.Label(self.body, text=self.tr("target_desc"), bg="#f5f7fb", fg="#687385", wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 16))
        ttk.Radiobutton(self.body, text=self.tr("mode_normal"), variable=self.mode_var, value="normal").pack(anchor=tk.W, pady=4)
        ttk.Radiobutton(self.body, text=self.tr("mode_portable"), variable=self.mode_var, value="portable").pack(anchor=tk.W, pady=4)

        row = tk.Frame(self.body, bg="#f5f7fb")
        row.pack(fill=tk.X, pady=(22, 0))
        tk.Label(row, text=self.tr("install_to"), bg="#f5f7fb", fg="#1d2636").pack(anchor=tk.W)
        entry_row = tk.Frame(row, bg="#f5f7fb")
        entry_row.pack(fill=tk.X, pady=8)
        ttk.Entry(entry_row, textvariable=self.target_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(entry_row, text=self.tr("browse"), command=self._browse_target).pack(side=tk.LEFT, padx=(8, 0))

    def _page_components(self) -> None:
        tk.Label(self.body, text=self.tr("components_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        tk.Label(self.body, text=self.tr("components_desc"), bg="#f5f7fb", fg="#687385", wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 18))
        card = tk.Frame(self.body, bg="#ffffff", highlightbackground="#dfe4ee", highlightthickness=1, padx=16, pady=14)
        card.pack(fill=tk.X)
        ttk.Checkbutton(card, text=self.tr("tag_editor_component"), variable=self.tag_editor_var).pack(anchor=tk.W)
        tk.Label(card, text=self.tr("tag_editor_desc"), bg="#ffffff", fg="#687385", wraplength=610, justify=tk.LEFT).pack(anchor=tk.W, pady=(8, 0))

    def _page_shortcuts(self) -> None:
        tk.Label(self.body, text=self.tr("shortcuts_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        tk.Label(self.body, text=self.tr("shortcuts_desc"), bg="#f5f7fb", fg="#687385", wraplength=620, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 18))
        ttk.Checkbutton(self.body, text=self.tr("desktop_shortcut"), variable=self.desktop_var).pack(anchor=tk.W, pady=6)
        ttk.Checkbutton(self.body, text=self.tr("start_menu_shortcut"), variable=self.start_menu_var).pack(anchor=tk.W, pady=6)

    def _page_summary(self) -> None:
        tk.Label(self.body, text=self.tr("summary_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        mode_text = self.tr("mode_normal") if self.mode_var.get() == "normal" else self.tr("mode_portable")
        shortcut_text = []
        if self.desktop_var.get():
            shortcut_text.append(self.tr("shortcut_desktop"))
        if self.start_menu_var.get():
            shortcut_text.append(self.tr("shortcut_start_menu"))
        if not shortcut_text:
            shortcut_text.append(self.tr("shortcut_none"))
        components = [self.tr("component_main")]
        if self.tag_editor_var.get():
            components.append(self.tr("component_tag_editor"))
        joiner = "、" if self.language_code() == "zh" else ", "
        summary = (
            f"{self.tr('summary_app')}：{APP_TITLE} / MemeFinder\n"
            f"{self.tr('summary_version')}：{VERSION}\n"
            f"{self.tr('summary_location')}：{self.target_var.get()}\n"
            f"{self.tr('summary_mode')}：{mode_text}\n"
            f"{self.tr('summary_shortcuts')}：{joiner.join(shortcut_text)}\n"
            f"{self.tr('summary_components')}：{joiner.join(components)}"
        )
        tk.Label(self.body, text=summary, bg="#ffffff", fg="#1d2636", justify=tk.LEFT, anchor=tk.W, padx=18, pady=18, relief=tk.FLAT, wraplength=620).pack(fill=tk.X, pady=18)

    def _page_installing(self) -> None:
        tk.Label(self.body, text=self.tr("installing_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(self.body, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, pady=(24, 12))
        self.progress_bar.start(12)
        tk.Label(self.body, textvariable=self.status_var, bg="#f5f7fb", fg="#3d4654", wraplength=620, justify=tk.LEFT).pack(anchor=tk.W)
        if not self.installing:
            self._start_install()

    def _page_done(self) -> None:
        tk.Label(self.body, text=self.tr("done_title"), bg="#f5f7fb", fg="#1d2636", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor=tk.W)
        tk.Label(self.body, text=self.tr("done_body", path=self.installed_dir), bg="#f5f7fb", fg="#3d4654", justify=tk.LEFT, wraplength=620).pack(anchor=tk.W, pady=18)
        ttk.Checkbutton(self.body, text=self.tr("launch_after"), variable=self.launch_var).pack(anchor=tk.W, pady=8)

    def _browse_target(self) -> None:
        initial = Path(self.target_var.get()).expanduser()
        directory = filedialog.askdirectory(title=self.tr("choose_target"), initialdir=str(initial.parent if initial.parent.exists() else default_install_dir().parent))
        if directory:
            self.target_var.set(directory)

    def _next(self) -> None:
        if self.page_index == self.PAGE_SUMMARY:
            if not self.target_var.get().strip():
                messagebox.showerror(self.tr("setup_title"), self.tr("target_required"))
                return
            self.page_index = self.PAGE_INSTALLING
            self._render_page()
            return
        if self.page_index == self.PAGE_DONE:
            self._finish()
            return
        self.page_index = min(self.PAGE_DONE, self.page_index + 1)
        self._render_page()

    def _back(self) -> None:
        self.page_index = max(self.PAGE_WELCOME, self.page_index - 1)
        self._render_page()

    def _cancel(self) -> None:
        if messagebox.askyesno(self.tr("setup_title"), self.tr("confirm_cancel")):
            self.destroy()

    def _start_install(self) -> None:
        self.installing = True
        target = Path(self.target_var.get())
        mode = self.mode_var.get()
        desktop = self.desktop_var.get()
        start_menu = self.start_menu_var.get()
        include_tag_editor = self.tag_editor_var.get()
        language = self.language_code()

        def worker() -> None:
            try:
                installed = install_application(
                    target,
                    mode,
                    desktop,
                    start_menu,
                    include_tag_editor,
                    language,
                    progress=lambda message: self.install_queue.put(("progress", message)),
                )
                self.install_queue.put(("done", installed))
            except Exception as exc:  # noqa: BLE001
                self.install_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_install)

    def _poll_install(self) -> None:
        while True:
            try:
                kind, payload = self.install_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.status_var.set(str(payload))
            elif kind == "done":
                self.installed_dir = Path(payload)
                self.installing = False
                self.page_index = self.PAGE_DONE
                self._render_page()
                return
            elif kind == "error":
                self.installing = False
                messagebox.showerror(self.tr("setup_title"), self.tr("install_failed", error=payload))
                self.page_index = self.PAGE_SUMMARY
                self._render_page()
                return
        if self.installing:
            self.after(100, self._poll_install)

    def _finish(self) -> None:
        if self.launch_var.get() and self.installed_dir:
            exe = self.installed_dir / "MemeFinder.exe"
            if exe.exists():
                subprocess.Popen([str(exe)], cwd=str(self.installed_dir))
        self.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SETUP_TITLE)
    parser.add_argument("--silent", action="store_true", help="Run without the graphical setup wizard.")
    parser.add_argument("--target", default=str(default_install_dir()), help="Install target directory.")
    parser.add_argument("--mode", choices=["normal", "portable"], default="normal", help="Data mode.")
    parser.add_argument("--language", choices=["zh", "en"], default="zh", help="Installer language for silent progress output.")
    parser.add_argument("--include-tag-editor", action="store_true", help="Install the experimental Tag Data Editor component.")
    parser.add_argument("--desktop-shortcut", action="store_true", help="Create a desktop shortcut in silent mode.")
    parser.add_argument("--start-menu-shortcut", action="store_true", help="Create a Start Menu shortcut in silent mode.")
    parser.add_argument("--no-shortcuts", action="store_true", help="Do not create shortcuts in silent mode.")
    parser.add_argument("--launch", action="store_true", help="Launch the app after silent install.")
    return parser.parse_args()


def write_silent_error(exc: Exception) -> Path:
    temp_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or Path.cwd())
    log_path = temp_dir / "MemeFinderSetup-error.log"
    log_path.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
    return log_path


def safe_print(message: object) -> None:
    try:
        print(message, flush=True)
    except OSError:
        pass


def main() -> int:
    args = parse_args()
    if args.silent:
        try:
            desktop = False if args.no_shortcuts else args.desktop_shortcut
            start_menu = False if args.no_shortcuts else args.start_menu_shortcut
            target = install_application(
                Path(args.target),
                args.mode,
                desktop,
                start_menu,
                args.include_tag_editor,
                args.language,
                progress=safe_print,
            )
            if args.launch:
                subprocess.Popen([str(target / "MemeFinder.exe")], cwd=str(target))
            safe_print(f"INSTALLED={target}")
            return 0
        except Exception as exc:  # noqa: BLE001
            log_path = write_silent_error(exc)
            safe_print(f"ERROR_LOG={log_path}")
            return 1

    app = SetupWizard()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
