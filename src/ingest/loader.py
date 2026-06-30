"""
文档加载器 —— 递归扫描目录，读取 .md / .txt 文件。

设计思路：
    用一个 Document 数据类统一表示被加载的文档，
    方便下游模块（分块器、嵌入器）消费。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Document:
    """一篇已加载的文档"""
    path: Path                # 文件路径
    content: str              # 文件正文
    filename: str = ""        # 文件名（不含路径）
    size_bytes: int = 0       # 文件大小
    metadata: dict = field(default_factory=dict)  # 额外元数据


def load_directory(
    root_dir: str | Path,
    glob_patterns: tuple[str, ...] = ("*.md", "*.txt", "*.markdown"),
    recursive: bool = True,
    max_file_size_mb: float = 50.0,
) -> list[Document]:
    """
    递归扫描目录，加载所有匹配的文档。

    Args:
        root_dir:     要扫描的根目录
        glob_patterns: 文件匹配模式
        recursive:    是否递归子目录
        max_file_size_mb: 跳过超过此大小的文件

    Returns:
        Document 列表。如果目录不存在，返回空列表。
    """
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []

    max_bytes = int(max_file_size_mb * 1024 * 1024)
    documents: list[Document] = []

    for pattern in glob_patterns:
        matches = root.rglob(pattern) if recursive else root.glob(pattern)
        for file_path in matches:
            # 跳过隐藏文件和目录
            if _is_hidden(file_path):
                continue

            # 检查文件大小
            size = file_path.stat().st_size
            if size > max_bytes:
                continue

            doc = _load_single_file(file_path)
            if doc:
                documents.append(doc)

    return documents


def _load_single_file(file_path: Path) -> Optional[Document]:
    """读取单个文件，尝试多种编码"""
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            content = file_path.read_text(encoding=enc)
            return Document(
                path=file_path,
                content=content,
                filename=file_path.name,
                size_bytes=file_path.stat().st_size,
                metadata={
                    "encoding": enc,
                    "suffix": file_path.suffix,
                },
            )
        except (UnicodeDecodeError, PermissionError):
            continue
    return None


def _is_hidden(path: Path) -> bool:
    """判断文件/目录是否为隐藏（Windows + 通用规则）"""
    # 文件名以 . 开头
    if path.name.startswith("."):
        return True
    # Windows 隐藏属性
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != -1 and attrs & FILE_ATTRIBUTE_HIDDEN:
            return True
    except Exception:
        pass
    return False
