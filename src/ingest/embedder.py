"""
嵌入模型接口 —— 统一不同提供商的嵌入模型调用。

支持的提供商：
    local:   使用 sentence-transformers 本地运行（免费，推荐中文 BGE 系列）
    openai:  调用 OpenAI 兼容 API（含 DeepSeek、Ollama 等）
    ollama:  调用本地 Ollama 服务

所有实现遵循统一接口：embed(texts: list[str]) -> list[list[float]]
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseEmbedder(ABC):
    """嵌入模型抽象基类"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        将文本列表转换为向量列表。

        Args:
            texts: 文本字符串列表

        Returns:
            向量列表，每个向量是 float 列表，长度与 texts 一致
        """
        ...

    @abstractmethod
    def dimension(self) -> int:
        """返回当前模型的向量维度"""
        ...


# ============================================================
# 本地 sentence-transformers 实现
# ============================================================

class LocalEmbedder(BaseEmbedder):
    """
    使用 sentence-transformers 本地运行嵌入模型。

    首次加载时自动下载模型到本地缓存，之后无需网络。
    推荐模型:
        BAAI/bge-small-zh-v1.5   (512维, 中文友好, ~100MB)
        BAAI/bge-large-zh-v1.5   (1024维, 更准但更慢)
        all-MiniLM-L6-v2          (384维, 英文为主)
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None
        self._dim = 0

    def _load_model(self):
        """延迟加载模型（首次调用 embed 时才下载）"""
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name)
        self._dim = self._model.get_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        # 注意：encode 返回 numpy array，转为 Python list
        embeddings = self._model.encode(  # type: ignore[union-attr]
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def dimension(self) -> int:
        self._load_model()
        return self._dim


# ============================================================
# OpenAI 兼容 API 实现
# ============================================================

class OpenAIEmbedder(BaseEmbedder):
    """
    调用 OpenAI 兼容的嵌入 API。

    适用服务:
        - OpenAI text-embedding-3-small / text-embedding-3-large
        - 任何兼容 OpenAI embedding 接口的第三方服务
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dimension: int = 1536,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._dim = dimension
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        resp = client.embeddings.create(model=self.model, input=texts)
        # 按输入顺序排列
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]

    def dimension(self) -> int:
        return self._dim


# ============================================================
# 工厂函数
# ============================================================

def create_embedder(config) -> BaseEmbedder:
    """
    根据配置创建嵌入模型实例。

    Args:
        config: AppConfig 对象（来自 src.config.manager）

    Returns:
        BaseEmbedder 实例
    """
    provider = config.embedding.provider
    model = config.embedding.model
    api_key = config.embedding.api_key
    base_url = config.embedding.base_url
    dim = config.embedding.dimension

    if provider == "local":
        return LocalEmbedder(model_name=model)

    elif provider == "openai":
        return OpenAIEmbedder(model=model, api_key=api_key, base_url=base_url, dimension=dim)

    elif provider == "ollama":
        # Ollama 也走 OpenAI 兼容协议，base_url 默认为 http://localhost:11434/v1
        ollama_url = base_url or "http://localhost:11434/v1"
        return OpenAIEmbedder(model=model, base_url=ollama_url, dimension=dim)

    else:
        raise ValueError(f"不支持的嵌入模型提供商: {provider}")
