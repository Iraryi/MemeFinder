# MemeFinder / 梗图搜查器

**A local image-memory search tool for finding the exact meme, screenshot, reaction image, or visual reference you only vaguely remember.**  
**一个本地图片记忆检索工具：用“我记得它大概长什么样、表达什么意思、图里有什么字”来找回那张图。**

[Download latest Setup / 下载最新版安装包](https://github.com/Iraryi/MemeFinder/releases/latest/download/MemeFinder-Setup.exe)

> Private by design: MemeFinder builds a local searchable DATA library on your own machine. You decide whether to use OCR, AI tagging, manual tags, or imported tag data.

---

<details open>
<summary><strong>中文介绍：点击展开 / 收起</strong></summary>

## 这是什么？

梗图搜查器是一个面向普通用户的本地图片检索工具。它不是普通的文件名搜索，而是把图片整理成“可被记住的线索”：图片文字、画面物体、图片结构、图片意义、用户备注、标签状态等。

你可以用很模糊的印象找图，例如：

- “那张聊天截图里好像有一句很阴阳怪气的话”
- “画面像表格，右边有个红色标注”
- “一个适合表达尴尬、无语、反转的梗图”
- “我记得这张图以前在某个目录，但后来整批图片搬家了”

## 它能做什么？

- **本地 DATA 检索**：把图片路径、OCR 文字、AI 识图结果、手写备注保存到本机数据库。
- **按意义找图**：不仅搜文件名，还能搜“图片意义”“情绪”“用途”“场景感”。
- **批量标签**：批量 OCR 和可选 AI 识图，快速建立可搜索资料库。
- **手动标签**：逐张浏览图片，补充文字、物体、结构、意义和备注。
- **检索范围管理**：支持搜索根目录、黑名单、白名单预设、导入导出和重扫。
- **数据导入导出**：完整 DATA、标签数据、检索范围都可以拆分管理。
- **实验性标签数据编辑器**：Setup 中可选安装 Tag Data Editor - Experimental，用于批量修改导出的标签数据 JSON，例如批量迁移旧目录路径到新目录路径。
- **便携模式**：可把数据保存在安装目录内，适合移动硬盘、同步盘或多设备迁移。
- **卸载入口**：安装目录内包含 UNINSTALL.bat，默认保留 DATA，便携数据会先备份。

## 用途有多广？

它适合任何“图片很多，但你记不清文件名”的场景：

- 梗图、表情包、反应图、聊天截图收藏
- 社交媒体素材、截图证据、灵感图库
- 设计参考、构图参考、UI 截图库
- 漫画分镜、视频截图、游戏截图
- 历史资料、新闻截图、研究图片、课程素材
- 个人知识库里的图片附件和长期归档

## 怎么使用？

1. 在 Releases 下载 MemeFinder-Setup.exe。
2. 运行安装器，选择普通模式或便携模式。
3. 第一次启动正式软件时，先在 “请选择语言 / Please choose a language” 窗口中选择语言。
4. 打开 “设置 > 检索范围”，添加要搜索的图片目录和黑名单。
5. 进入 “批量标签”，点击开始建立 DATA。
6. 回到主菜单或高级搜索，用关键词、画面元素、含义、备注来找图。
7. 如果需要精修结果，进入 “手动标签” 给图片补充记忆。

## 打包开发版

    py -3.10 -m pip install -r requirements.txt
    .\build.ps1
    .\build_setup.ps1

生成的发布安装包位于：

    release\MemeFinder-Setup.exe

</details>

---

<details>
<summary><strong>English Introduction: click to expand / collapse</strong></summary>

## What is MemeFinder?

MemeFinder is a local image-memory search tool for people who remember the content, mood, structure, or meaning of an image better than its file name.

Instead of only indexing file names, it helps turn images into searchable memory clues: visible text, objects, visual structure, semantic meaning, personal notes, and tagging status.

You can search with fuzzy memories such as:

- “a sarcastic chat screenshot with a short line of text”
- “a table-like image with a red annotation on the right”
- “a reaction image for embarrassment, silence, irony, or reversal”
- “a whole image collection moved from one folder path to another”

## What can it do?

- **Local searchable DATA**: stores image paths, OCR text, AI vision summaries, manual notes, and status flags locally.
- **Meaning-based search**: search not only by file name, but also by mood, usage, visual structure, and semantic meaning.
- **Batch tagging**: batch OCR and optional AI vision analysis to build a searchable image library.
- **Manual tagging**: browse images one by one and refine text, objects, structure, meaning, and notes.
- **Search scope management**: root folders, blacklists, whitelist presets, import/export, and rescanning.
- **Data import/export**: manage complete DATA, tag-data-only JSON, and search scopes separately.
- **Experimental Tag Data Editor**: optional Setup component for batch-editing exported tag-data JSON files, including path-prefix migration.
- **Portable mode**: keep data inside the install folder for removable drives, sync folders, or easy migration.
- **Uninstall entry**: installed folders include UNINSTALL.bat; saved DATA is kept by default.

## Why is it broadly useful?

MemeFinder is useful whenever you have lots of images but cannot remember their names:

- meme, sticker, reaction image, and chat screenshot collections
- social media materials, visual evidence, inspiration boards
- design references, layout references, UI screenshot libraries
- comic panels, video frames, game screenshots
- historical materials, news screenshots, research images, teaching resources
- personal knowledge-base attachments and long-term visual archives

## How to use it

1. Download MemeFinder-Setup.exe from Releases.
2. Run the Setup and choose normal mode or portable mode.
3. On first launch, choose a language in the bilingual “请选择语言 / Please choose a language” window.
4. Open Settings > Search Scope and add image folders plus blacklist folders.
5. Go to Batch Tagging and build the local DATA library.
6. Search from the home page or advanced search using text, objects, meaning, visual clues, or notes.
7. Use Manual Tagging to refine important images.

## Build from source

    py -3.10 -m pip install -r requirements.txt
    .\build.ps1
    .\build_setup.ps1

The release installer is generated at:

    release\MemeFinder-Setup.exe

</details>

---

## Release Asset

The Setup installer is published as a GitHub Release asset:

    MemeFinder-Setup.exe

