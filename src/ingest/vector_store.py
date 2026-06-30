"""
向量数据库封装 —— 基于 ChromaDB，提供文档的存储与检索。

ChromaDB 是一个轻量级本地向量数据库，数据持久化到磁盘，
无需额外部署服务，完美适合个人知识库场景。
"""

from pathlib import Path
from typing import Optional


class VectorStore:
    """
    ChromaDB 本地向量存储。

    用法:
        store = VectorStore("./chroma_db")
        store.add(chunks, embeddings)
        results = store.query(query_embedding, top_k=5)
    """

    def __init__(self, persist_dir: str | Path):
        """
        Args:
            persist_dir: ChromaDB 数据持久化目录
        """
        self.persist_dir = str(persist_dir)
        self._client = None
        self._collection = None

    def _init(self):
        """延迟初始化 ChromaDB（避免启动时就加载）"""
        if self._client is not None:
            return
        import chromadb
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="research_docs",
            metadata={"hnsw:space": "cosine"},  # 余弦相似度
        )

    # ---- 写入 ----

    def add(
        self,
        chunks: list,       # list[Chunk]，避免循环导入
        embeddings: list[list[float]],
    ) -> int:
        """
        将文本块及其向量写入数据库。

        Args:
            chunks:     Chunk 对象列表
            embeddings: 对应的向量列表（顺序一致）

        Returns:
            写入的条数
        """
        self._init()
        if not chunks:
            return 0

        ids = [f"{chunk.source_file}_{chunk.chunk_index}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "source_file": chunk.source_file,
                "chunk_index": chunk.chunk_index,
                "source_path": chunk.metadata.get("source_path", ""),
            }
            for chunk in chunks
        ]

        # 使用 upsert 避免重复：相同 id 自动覆盖
        self._collection.upsert(  # type: ignore[union-attr]
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    # ---- 检索 ----

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        从向量库中检索最相似的文本块。

        Args:
            query_embedding: 查询向量
            top_k:           返回条数
            where:           可选过滤条件（如按文件名过滤）

        Returns:
            结果列表，每项包含 {text, source_file, chunk_index, distance}
        """
        self._init()
        if self._collection is None or self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # 规范化返回格式
        output: list[dict] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "source_file": results["metadatas"][0][i].get("source_file", "") if results["metadatas"] else "",
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", 0) if results["metadatas"] else 0,
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return output

    # ---- 管理 ----

    def count(self) -> int:
        """返回当前向量库中存储的数量"""
        self._init()
        if self._collection is None:
            return 0
        return self._collection.count()

    def clear(self) -> None:
        """清空向量库"""
        self._init()
        if self._client is not None:
            try:
                self._client.delete_collection("research_docs")
            except Exception:
                pass
            self._collection = self._client.get_or_create_collection("research_docs")

    def get_stats(self) -> dict:
        """获取向量库统计信息"""
        self._init()
        count = self._collection.count() if self._collection else 0

        # 获取唯一文件列表
        files = set()
        if self._collection and count > 0:
            # 取一批数据来提取文件名
            sample = self._collection.get(limit=min(count, 10000), include=["metadatas"])
            if sample["metadatas"]:
                for meta in sample["metadatas"]:
                    files.add(meta.get("source_file", "未知"))

        return {
            "count": count,
            "files": sorted(files),
            "persist_dir": self.persist_dir,
        }
