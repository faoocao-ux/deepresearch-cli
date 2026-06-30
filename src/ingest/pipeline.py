"""
摄取管道 —— 将「加载 → 分块 → 向量化 → 存储」串联为一步操作。

整个流程:
    1. 扫描目录找到所有 .md / .txt
    2. 按语义边界切分每个文档为文本块
    3. 用嵌入模型将文本块转为向量
    4. 存入 ChromaDB

同时支持批量处理（一次 embedding 一批文本块，提高效率）。
"""

from pathlib import Path
from typing import Optional

from src.config.manager import AppConfig
from src.ingest.loader import Document, load_directory
from src.ingest.chunker import Chunk, chunk_documents
from src.ingest.embedder import BaseEmbedder, create_embedder
from src.ingest.vector_store import VectorStore


# 批量嵌入的批次大小（避免一次传太多文本导致 OOM）
BATCH_SIZE = 32


def run_ingest(
    config: AppConfig,
    target_dir: Optional[str] = None,
    progress_callback=None,
) -> dict:
    """
    执行完整的文档摄取流程。

    Args:
        config:            应用配置
        target_dir:        要摄取的目录，None 则使用配置中的 books_dir
        progress_callback: 可选回调函数 fn(stage, current, total, message)

    Returns:
        统计信息字典: {files, chunks, duration_seconds}
    """
    import time
    start_time = time.time()

    # ---- 确定目标目录 ----
    if target_dir:
        scan_dir = Path(target_dir)
    else:
        # books_dir 可能是相对路径，以 obsidian_path 为基准
        obsidian = Path(config.obsidian_path)
        books = Path(config.books_dir)
        scan_dir = obsidian / books if not books.is_absolute() else books

    # ---- Step 1: 加载文档 ----
    _report(progress_callback, "load", 0, 4, f"扫描目录: {scan_dir}")
    documents = load_directory(scan_dir)
    if not documents:
        return {"files": 0, "chunks": 0, "duration_seconds": time.time() - start_time}

    _report(progress_callback, "load", 1, 4, f"找到 {len(documents)} 个文件")

    # ---- Step 2: 文本分块 ----
    _report(progress_callback, "chunk", 1, 4, "正在切分文本...")
    chunks = chunk_documents(
        documents,
        chunk_size=config.chunk.chunk_size,
        chunk_overlap=config.chunk.chunk_overlap,
        separators=config.chunk.separators,
    )
    _report(progress_callback, "chunk", 2, 4, f"生成 {len(chunks)} 个文本块")

    # ---- Step 3: 向量化（批量） ----
    _report(progress_callback, "embed", 2, 4, "正在向量化...")
    embedder = create_embedder(config)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c.text for c in batch]
        embeddings = embedder.embed(texts)
        all_embeddings.extend(embeddings)

    _report(progress_callback, "embed", 3, 4, f"向量化完成，维度={embedder.dimension()}")

    # ---- Step 4: 分批写入 ChromaDB ----
    _report(progress_callback, "store", 3, 4, "正在写入向量库...")

    # ChromaDB 存储路径：绝对路径或相对于 obsidian_path
    chroma = Path(config.chroma_dir)
    if not chroma.is_absolute():
        chroma = Path(config.obsidian_path) / chroma

    store = VectorStore(str(chroma))

    # 分批写入，避免一次性写入过多导致索引构建失败
    WRITE_BATCH = 200
    total_written = 0
    for i in range(0, len(chunks), WRITE_BATCH):
        batch_chunks = chunks[i:i + WRITE_BATCH]
        batch_embeddings = all_embeddings[i:i + WRITE_BATCH]
        store.add(batch_chunks, batch_embeddings)
        total_written += len(batch_chunks)
        _report(progress_callback, "store", 3, 4, f"正在写入向量库... ({total_written}/{len(chunks)})")

    _report(progress_callback, "store", 4, 4, f"已写入 {total_written} 条向量")

    elapsed = time.time() - start_time
    return {
        "files": len(documents),
        "chunks": len(chunks),
        "duration_seconds": round(elapsed, 1),
    }


def _report(callback, stage, current, total, message):
    """内部辅助：安全调用进度回调"""
    if callback:
        try:
            callback(stage, current, total, message)
        except Exception:
            pass
