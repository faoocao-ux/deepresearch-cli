"""
CLI 入口 —— 研究工具命令行接口

命令一览：
    research init      初始化项目配置
    research config    查看/修改配置
    research convert   文档格式转换（PDF/EPUB/DOCX/HTML → .md）
    research ingest    摄取文档到向量库
    research ask       向知识库提问
    research status    查看索引进度
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config.manager import ConfigManager
from src.ingest.pipeline import run_ingest
from src.query.rag import RAGPipeline
from src.tools.doc_converter import convert_file, convert_directory, SUPPORTED_FORMATS

# 创建 Typer 应用和 Rich 控制台
app = typer.Typer(
    name="research",
    help="[研究工具] 本地 CLI 研究工具 -- 结合 Obsidian 书籍库 + 向量检索 + LLM 推理",
    add_completion=False,
)
console = Console()

# 全局配置管理器实例
cfg = ConfigManager()


# ============================================================
# init — 初始化项目
# ============================================================

@app.command()
def init(
    obsidian_path: str = typer.Option(
        ...,
        "--obsidian-path", "-p",
        prompt="请输入 Obsidian 知识库的根目录路径",
        help="Obsidian 知识库根目录",
    ),
):
    """
    初始化研究工具，生成默认配置文件。

    示例：
        research init
        research init --obsidian-path "G:/MyObsidianVault"
    """
    console.print(f"\n[bold cyan][初始化] 正在初始化研究工具...[/bold cyan]")

    # 验证路径
    obsidian = Path(obsidian_path)
    if not obsidian.exists():
        console.print(f"[yellow][警告] 路径不存在: {obsidian_path}[/yellow]")
        console.print("[yellow]       配置文件已生成，但请确认路径是否正确。[/yellow]")
    elif not obsidian.is_dir():
        console.print(f"[red][错误] 路径不是目录: {obsidian_path}[/red]")
        raise typer.Exit(1)

    # 生成配置
    config_path = cfg.init(str(obsidian.resolve()))

    console.print(f"[green][成功] 配置文件已生成: {config_path}[/green]")
    console.print(f"[green]        Obsidian 路径: {obsidian.resolve()}[/green]")
    console.print("\n[bold]下一步：[/bold]")
    console.print("  1. 编辑配置文件: research config show")
    console.print("  2. 放入书籍到 Obsidian 目录的 books 子文件夹")
    console.print("  3. 摄取文档:         research ingest")
    console.print("  4. 开始提问:         research ask \"你的问题\"")


# ============================================================
# config — 查看/修改配置
# ============================================================

config_app = typer.Typer(help="查看和修改配置")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """
    显示当前完整配置。

    示例：
        research config show
    """
    config = cfg.load()
    console.print(f"\n[bold cyan][配置] 当前配置[/bold cyan]")
    console.print(f"[dim]配置文件: {cfg.config_path}[/dim]\n")

    # 使用 Rich 表格展示关键配置
    table = Table(title="核心配置", show_header=False, border_style="dim")
    table.add_column("键", style="cyan", no_wrap=True)
    table.add_column("值", style="white")

    table.add_row("obsidian_path", config.obsidian_path or "[red]未设置[/red]")
    table.add_row("books_dir", config.books_dir)
    table.add_row("chroma_dir", config.chroma_dir)
    table.add_row("embedding.provider", config.embedding.provider)
    table.add_row("embedding.model", config.embedding.model)
    table.add_row("llm.provider", config.llm.provider)
    table.add_row("llm.model", config.llm.model)
    table.add_row("chunk.chunk_size", str(config.chunk.chunk_size))
    table.add_row("chunk.chunk_overlap", str(config.chunk.chunk_overlap))
    table.add_row("top_k", str(config.top_k))

    console.print(table)
    console.print("\n[dim]运行 'research config show --raw' 查看完整 YAML[/dim]")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置键（点号分隔），如 llm.model"),
    value: str = typer.Argument(..., help="配置值"),
):
    """
    修改配置项。

    示例：
        research config set llm.model "claude-opus-4-8"
        research config set embedding.provider "openai"
        research config set top_k 10
    """
    try:
        # 尝试转换值的类型
        typed_value = _convert_value(value)
        cfg.set(key, typed_value)
        console.print(f"[green][成功] {key} = {typed_value}[/green]")
        console.print(f"[dim]配置已保存到: {cfg.config_path}[/dim]")
    except (AttributeError, KeyError) as e:
        console.print(f"[red][错误] 无效的配置键: {key} ({e})[/red]")
        raise typer.Exit(1)


# ============================================================
# status — 查看工具状态
# ============================================================

@app.command()
def status():
    """
    查看研究工具当前状态（已索引文档数、向量库大小等）。

    示例：
        research status
    """
    config = cfg.load()

    if not config.obsidian_path:
        console.print("[red][错误] 请先运行 research init 设置 Obsidian 路径[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan][状态] 研究工具状态[/bold cyan]\n")

    # 基本信息
    info_table = Table(show_header=False, border_style="dim", title="基本信息")
    info_table.add_column("项", style="cyan")
    info_table.add_column("值", style="white")
    info_table.add_row("Obsidian 路径", config.obsidian_path)
    info_table.add_row("书籍目录", str(Path(config.obsidian_path) / config.books_dir))
    info_table.add_row("LLM 模型", f"{config.llm.provider} / {config.llm.model}")
    info_table.add_row("嵌入模型", f"{config.embedding.provider} / {config.embedding.model}")
    console.print(info_table)

    # 向量库统计
    console.print()
    try:
        pipeline = RAGPipeline(config)
        stats = pipeline.get_store_stats()

        store_table = Table(show_header=False, border_style="dim", title="向量库统计")
        store_table.add_column("项", style="cyan")
        store_table.add_column("值", style="white")
        store_table.add_row("已索引块数", str(stats["count"]))
        store_table.add_row("存储路径", stats["persist_dir"])
        store_table.add_row("来源文件数", str(len(stats["files"])))

        if stats["files"]:
            file_list = "\n".join(f"  • {f}" for f in stats["files"][:20])
            if len(stats["files"]) > 20:
                file_list += f"\n  ... 共 {len(stats['files'])} 个文件"
            store_table.add_row("文件列表", file_list)

        console.print(store_table)
    except Exception as e:
        console.print(f"[yellow][提示] 向量库暂不可用: {e}[/yellow]")
        console.print("[dim]请先运行 research ingest 摄取文档[/dim]")


# ============================================================
# ingest / add / ask — 核心命令
# ============================================================

@app.command()
def ingest(
    directory: Optional[str] = typer.Option(
        None,
        "--dir", "-d",
        help="要摄取的目录（默认使用配置中的 books_dir）",
    ),
):
    """
    摄取文档到向量数据库。

    示例：
        research ingest
        research ingest --dir ./my_books
    """
    config = cfg.load()

    if not config.obsidian_path:
        console.print("[red][错误] 请先运行 research init 设置 Obsidian 路径[/red]")
        raise typer.Exit(1)

    # 显示启动信息
    target = directory or str(Path(config.obsidian_path) / config.books_dir)
    console.print(f"\n[bold cyan][摄取] 目标目录: {target}[/bold cyan]")

    # 使用 Rich 进度条运行摄取
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]准备中...", total=None)

        def on_progress(stage, current, total, message):
            progress.update(task_id, description=f"[cyan]{message}")

        try:
            result = run_ingest(config, directory, progress_callback=on_progress)
        except Exception as e:
            console.print(f"[red][错误] 摄取失败: {e}[/red]")
            raise typer.Exit(1)

    # 显示结果
    console.print(f"\n[green][成功] 摄取完成！[/green]")
    console.print(f"  文件数:   {result['files']}")
    console.print(f"  文本块:   {result['chunks']}")
    console.print(f"  耗时:     {result['duration_seconds']} 秒")
    console.print(f"\n[dim]现在可以用 research ask \"你的问题\" 来提问了[/dim]")


# ============================================================
# convert — 文档格式转换
# ============================================================

@app.command()
def convert(
    path: str = typer.Argument(..., help="输入文件或目录路径"),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="输出目录（默认与源文件同目录）",
    ),
):
    """
    将文档转换为 Markdown 格式，支持 PDF / EPUB / DOCX / HTML。

    示例：
        research convert book.pdf
        research convert book.epub -o ./books
        research convert ./downloads -o ./books    # 批量转换整个目录
    """
    import os
    input_path = Path(path)

    if not input_path.exists():
        console.print(f"[red][错误] 路径不存在: {path}[/red]")
        raise typer.Exit(1)

    if input_path.is_dir():
        # 批量转换目录
        console.print(f"\n[bold cyan][转换] 批量转换目录: {input_path}[/bold cyan]")
        console.print(f"[dim]支持格式: {', '.join(SUPPORTED_FORMATS.values())}[/dim]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("[cyan]扫描中...", total=None)
            try:
                results = convert_directory(str(input_path), output_dir)
            except Exception as e:
                console.print(f"[red][错误] 转换失败: {e}[/red]")
                raise typer.Exit(1)

        if not results:
            console.print("[yellow]未找到可转换的文件[/yellow]")
            return

        # 结果表格
        table = Table(title="转换结果", show_header=True, border_style="dim")
        table.add_column("输入文件", style="cyan")
        table.add_column("格式", style="white", width=8)
        table.add_column("章节/段落", style="green", width=10)
        table.add_column("输出文件", style="white")
        table.add_column("大小", style="dim", width=8)

        for r in results:
            table.add_row(
                r.input_path.name,
                r.format,
                str(r.pages_or_chapters),
                r.output_path.name,
                f"{r.size_kb} KB",
            )

        console.print()
        console.print(table)
        console.print(f"\n[green][成功] 共转换 {len(results)} 个文件[/green]")
        console.print(f"[dim]输出目录: {output_dir or input_path}[/dim]")
        console.print(f"[dim]下一步: research ingest --dir {Path(output_dir or str(input_path)).resolve()}[/dim]")

    else:
        # 单文件转换
        suffix = input_path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            console.print(f"[red][错误] 不支持的格式: {suffix}[/red]")
            console.print(f"[dim]支持: {', '.join(SUPPORTED_FORMATS.keys())}[/dim]")
            raise typer.Exit(1)

        console.print(f"\n[bold cyan][转换] {input_path.name}[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"[cyan]正在转换 {SUPPORTED_FORMATS[suffix]}...", total=None)
            try:
                result = convert_file(str(input_path), output_dir)
            except Exception as e:
                console.print(f"[red][错误] 转换失败: {e}[/red]")
                raise typer.Exit(1)

        console.print()
        console.print(f"[green][成功] 转换完成！[/green]")
        console.print(f"  格式:     {result.format}")
        console.print(f"  章节/页:  {result.pages_or_chapters}")
        console.print(f"  输出:     {result.output_path}")
        console.print(f"  大小:     {result.size_kb} KB")
        console.print(f"\n[dim]下一步: research ingest --dir {result.output_path.parent.resolve()}[/dim]")


# ============================================================
# add — 一键导入（自动识别 → 转换 → 摄取）
# ============================================================

@app.command()
def add(
    path: str = typer.Argument(..., help="要导入的文件或目录路径"),
):
    """
    一键导入：自动识别格式 → 转换 → 摄取到向量库。

    智能处理：
        .epub / .pdf / .docx / .html → 自动转换为 .md 后摄取
        .md / .txt / .markdown         → 直接摄取
        目录                            → 扫描后全部处理

    示例：
        research add book.epub
        research add ./downloads/
        research add 论文.pdf
    """
    import time
    input_path = Path(path)

    if not input_path.exists():
        console.print(f"[red][错误] 路径不存在: {path}[/red]")
        raise typer.Exit(1)

    config = cfg.load()
    if not config.obsidian_path:
        console.print("[red][错误] 请先运行 research init 设置 Obsidian 路径[/red]")
        raise typer.Exit(1)

    books_dir = Path(config.obsidian_path) / config.books_dir
    if not books_dir.is_absolute():
        books_dir = Path(config.obsidian_path) / books_dir
    books_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    new_md_files: list[Path] = []

    # ---- 收集待处理文件 ----
    to_process: list[Path] = []
    if input_path.is_dir():
        for ext in SUPPORTED_FORMATS:
            to_process.extend(input_path.rglob(f"*{ext}"))
        # 也收集已有的 md/txt
        for ext in ("*.md", "*.txt", "*.markdown"):
            to_process.extend(input_path.rglob(ext))
    else:
        to_process = [input_path]

    console.print(f"\n[bold cyan][一键导入] 找到 {len(to_process)} 个文件[/bold cyan]\n")

    # ---- 逐文件处理 ----
    for file_path in to_process:
        if file_path.name.startswith("."):
            continue

        suffix = file_path.suffix.lower()

        # 已是 md/txt → 直接拷贝到 books
        if suffix in (".md", ".txt", ".markdown"):
            dest = books_dir / file_path.name
            if dest != file_path:
                dest.write_bytes(file_path.read_bytes())
            new_md_files.append(dest)
            console.print(f"  [green]✓[/green] {file_path.name} [dim]→ 直接导入[/dim]")
            continue

        # 需转换的格式
        if suffix in SUPPORTED_FORMATS:
            console.print(f"  [cyan]→[/cyan] {file_path.name} [dim]正在转换 {SUPPORTED_FORMATS[suffix]}...[/dim]")
            try:
                result = convert_file(str(file_path), str(books_dir))
                new_md_files.append(result.output_path)
                console.print(f"  [green]✓[/green] {result.output_path.name} [dim]({result.pages_or_chapters}章, {result.size_kb}KB)[/dim]")
            except Exception as e:
                console.print(f"  [red]✗[/red] {file_path.name}: {e}")
                continue

    # ---- 摄取 ----
    md_files_in_books = list(books_dir.glob("*.md")) + list(books_dir.glob("*.txt"))
    if not md_files_in_books:
        console.print("\n[yellow]没有可摄取的 .md 文件[/yellow]")
        return

    console.print(f"\n[bold cyan][摄取] 正在将 {len(md_files_in_books)} 个文件写入向量库...[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]处理中...", total=None)

        def on_progress(stage, current, total, message):
            progress.update(task_id, description=f"[cyan]{message}")

        try:
            # 直接摄取整个 books 目录
            result = run_ingest(config, str(books_dir), progress_callback=on_progress)
        except Exception as e:
            console.print(f"[red][错误] 摄取失败: {e}[/red]")
            raise typer.Exit(1)

    elapsed = time.time() - start_time

    console.print(f"\n[green][完成] 一键导入成功！[/green]")
    console.print(f"  文件数: {result['files']}")
    console.print(f"  文本块: {result['chunks']}")
    console.print(f"  耗时:   {result['duration_seconds']} 秒")
    console.print(f"\n[dim]现在可以问了: research ask \"你的问题\"[/dim]")


@app.command()
def ask(
    question: str = typer.Argument(..., help="你想问的问题"),
    top_k: Optional[int] = typer.Option(
        None,
        "--top-k", "-k",
        help="检索的段落数（默认使用配置值）",
    ),
):
    """
    向知识库提问。基于向量检索 + LLM 推理生成回答。

    示例：
        research ask "什么是量子纠缠？"
        research ask "请总结《思考，快与慢》的核心观点"
        research ask "姚期智的主要贡献有哪些？" --top-k 10
    """
    config = cfg.load()

    if not config.obsidian_path:
        console.print("[red][错误] 请先运行 research init 设置 Obsidian 路径[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan][提问] {question}[/bold cyan]\n")

    # 使用 Rich 进度条
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]初始化...", total=None)

        def on_progress(stage, message):
            progress.update(task_id, description=f"[cyan]{message}")

        try:
            pipeline = RAGPipeline(config)
            result = pipeline.ask(question, top_k=top_k, progress_callback=on_progress)
        except Exception as e:
            console.print(f"[red][错误] 查询失败: {e}[/red]")
            raise typer.Exit(1)

    # ---- 显示结果 ----
    console.print()

    if result.context_chunks == 0:
        console.print(f"[yellow]{result.answer}[/yellow]")
        return

    # 回答
    console.print(f"[bold green]📖 回答[/bold green]")
    console.print(f"[white]{result.answer}[/white]")

    # 来源引用
    console.print(f"\n[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
    console.print(f"[bold cyan]📚 参考来源（共 {len(result.sources)} 段）[/bold cyan]")

    source_table = Table(show_header=True, border_style="dim")
    source_table.add_column("#", style="dim", width=3)
    source_table.add_column("来源文件", style="cyan")
    source_table.add_column("相似度", style="green", width=10)
    source_table.add_column("内容摘要", style="white", width=50)

    for i, src in enumerate(result.sources):
        text_preview = src.get("text", "")[:100].replace("\n", " ") + "..."
        distance = src.get("distance", 0)
        # 余弦距离转相似度（ChromaDB 用余弦距离，越小越相似）
        if distance <= 2.0:  # 余弦距离范围 [0, 2]
            similarity = f"{max(0, (1 - distance / 2)) * 100:.0f}%"
        else:
            similarity = f"{distance:.3f}"

        source_table.add_row(
            str(i + 1),
            src.get("source_file", "未知"),
            similarity,
            text_preview,
        )

    console.print(source_table)
    console.print(f"[dim]模型: {result.model}  |  上下文块: {result.context_chunks}[/dim]")


# ============================================================
# 辅助函数
# ============================================================

def _convert_value(value: str) -> any:
    """尝试将字符串值转换为合适的 Python 类型"""
    # bool
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    # int
    try:
        return int(value)
    except ValueError:
        pass
    # float
    try:
        return float(value)
    except ValueError:
        pass
    # null
    if value.lower() in ("null", "none"):
        return None
    # 默认字符串
    return value


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    app()
