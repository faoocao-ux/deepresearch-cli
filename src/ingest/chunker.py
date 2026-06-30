"""
文本分块器 —— 将长文档按语义边界切成更小的文本块。

策略：
    1. 优先按自然段落/句子分隔（配置中的 separators）
    2. 如果句子本身超过 chunk_size，回退到固定长度切割
    3. 相邻块之间保留 chunk_overlap 字符的重叠，避免切断上下文
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    """一个文本块"""
    text: str                           # 文本内容
    source_file: str = ""               # 来源文件名
    chunk_index: int = 0                # 在原文档中的块序号
    metadata: dict = field(default_factory=dict)


def split_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: Optional[list[str]] = None,
) -> list[str]:
    """
    将一段文本按分隔符递归切分为指定大小的块。

    Args:
        text:          原始文本
        chunk_size:    每块最大字符数
        chunk_overlap: 相邻块重叠字符数
        separators:    分隔符列表（优先级从高到低）

    Returns:
        字符串列表，每个元素为一个文本块
    """
    if separators is None:
        separators = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]

    # 空文本直接返回
    if not text or not text.strip():
        return []

    chunks: list[str] = []
    _split_recursive(text, separators, chunk_size, chunk_overlap, chunks)
    return chunks


def _split_recursive(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
    result: list[str],
) -> None:
    """递归切分：使用优先级最高的分隔符，不行则降级"""

    # 当前文本已经够短，直接收入
    if len(text) <= chunk_size:
        if text.strip():
            result.append(text.strip())
        return

    # 找到第一个有效的分隔符
    best_sep = ""
    best_splits: list[str] = []
    for sep in separators:
        if sep and sep in text:
            best_sep = sep
            best_splits = text.split(sep)
            break
        elif sep == "":
            # 兜底：无分隔符可用，强制按长度切
            best_sep = ""
            best_splits = [text]
            break

    if not best_splits:
        if text.strip():
            result.append(text.strip())
        return

    # 对于空字符串分隔符（强制切割），直接按长度处理
    if best_sep == "":
        _split_by_fixed_length(text, chunk_size, chunk_overlap, result)
        return

    # 用分隔符 split 后，逐段拼接
    current = ""
    for split_part in best_splits:
        piece = split_part + (best_sep if best_sep and split_part != best_splits[-1] else "")

        if len(current) + len(piece) <= chunk_size:
            current += piece
        else:
            # 当前 accumulation 够长了，存起来
            if current.strip():
                result.append(current.strip())
            # 新的 piece 是否过长？
            if len(piece) > chunk_size:
                _split_recursive(piece, separators[1:], chunk_size, chunk_overlap, result)
                current = ""
            else:
                # 重叠：从上一块的末尾取 overlap 字符
                if result and chunk_overlap > 0:
                    prev = result[-1]
                    overlap_text = prev[-chunk_overlap:] if len(prev) > chunk_overlap else prev
                    current = overlap_text + piece
                else:
                    current = piece

    # 处理尾部剩余
    if current.strip():
        result.append(current.strip())


def _split_by_fixed_length(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    result: list[str],
) -> None:
    """兜底策略：按固定字符数切割"""
    text = text.strip()
    if not text:
        return

    step = chunk_size - chunk_overlap
    if step <= 0:
        step = chunk_size

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            result.append(chunk)
        start += step


def chunk_documents(
    documents: list,  # list[Document]，避免循环导入
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: Optional[list[str]] = None,
) -> list[Chunk]:
    """
    对多篇文档统一分块。

    Args:
        documents:     Document 对象列表（来自 loader.py）
        chunk_size:    每块最大字符数
        chunk_overlap: 相邻块重叠字符数
        separators:    分隔符列表

    Returns:
        Chunk 对象列表
    """
    all_chunks: list[Chunk] = []

    for doc in documents:
        texts = split_text(doc.content, chunk_size, chunk_overlap, separators)
        for i, text in enumerate(texts):
            all_chunks.append(Chunk(
                text=text,
                source_file=doc.filename,
                chunk_index=i,
                metadata={
                    "source_path": str(doc.path),
                    "encoding": doc.metadata.get("encoding", "utf-8"),
                },
            ))

    return all_chunks
