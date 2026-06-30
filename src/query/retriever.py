"""
向量检索器 —— 将用户问题转为向量，从 ChromaDB 中召回最相关的文本块。

流程：
    1. 用嵌入模型将问题向量化
    2. 在向量库中搜索 top_k 个最相似的文本块
    3. 返回带元数据的检索结果
"""

from typing import Optional

from src.config.manager import AppConfig
from src.ingest.embedder import BaseEmbedder, create_embedder
from src.ingest.vector_store import VectorStore


class Retriever:
    """
    向量检索器 —— 封装"问题→向量→检索"的全流程。

    用法:
        retriever = Retriever(config)
        results = retriever.search("什么是量子计算？", top_k=5)
        # 返回: [{"text": "...", "source_file": "...", "distance": 0.23}, ...]
    """

    def __init__(self, config: AppConfig):
        """
        Args:
            config: 应用配置，用于初始化嵌入模型和向量库
        """
        self.config = config
        self._embedder: Optional[BaseEmbedder] = None
        self._store: Optional[VectorStore] = None

    def _ensure_initialized(self):
        """延迟初始化嵌入模型和向量库"""
        if self._embedder is None:
            self._embedder = create_embedder(self.config)

        if self._store is None:
            from pathlib import Path
            chroma = Path(self.config.chroma_dir)
            if not chroma.is_absolute():
                chroma = Path(self.config.obsidian_path) / chroma
            self._store = VectorStore(str(chroma))

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        根据查询文本检索最相关的文档块。

        Args:
            query: 用户问题 / 查询文本
            top_k: 返回条数（默认使用配置中的值）
            where: 可选过滤条件（按文件名等过滤）

        Returns:
            结果列表，每项包含 {id, text, source_file, chunk_index, distance}
        """
        self._ensure_initialized()

        k = top_k or self.config.top_k

        # 1. 将问题转为向量
        query_vec = self._embedder.embed([query])[0]  # type: ignore[union-attr]

        # 2. 检索
        results = self._store.query(query_vec, top_k=k, where=where)  # type: ignore[union-attr]

        return results

    def get_store_stats(self) -> dict:
        """获取向量库统计信息（供 status 命令使用）"""
        self._ensure_initialized()
        return self._store.get_stats()  # type: ignore[union-attr]
