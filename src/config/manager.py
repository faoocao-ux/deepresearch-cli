"""
配置管理器 —— 负责配置文件的读写、验证和模板生成。

配置文件路径：~/.deepresearch/config.yaml
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


# ============================================================
# 配置数据模型
# ============================================================

class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""
    provider: str = Field(
        default="local",
        description="嵌入模型提供商：local / openai / ollama"
    )
    model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="嵌入模型名称。本地：sentence-transformers 模型名；OpenAI：text-embedding-3-small"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API 密钥（OpenAI 等云端模型需要）"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="自定义 API 端点（Ollama 等本地部署）"
    )
    dimension: int = Field(
        default=512,
        description="向量维度（BGE-small-zh 为 512，OpenAI 为 1536）"
    )


class LLMConfig(BaseModel):
    """大语言模型配置"""
    provider: str = Field(
        default="anthropic",
        description="LLM 提供商：anthropic / openai / ollama"
    )
    model: str = Field(
        default="claude-sonnet-4-6",
        description="模型名称"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API 密钥"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="自定义 API 端点"
    )
    max_tokens: int = Field(
        default=4096,
        description="最大输出 token 数"
    )
    temperature: float = Field(
        default=0.3,
        description="生成温度（0=确定性，1=创造性）"
    )


class ChunkConfig(BaseModel):
    """文档分块配置"""
    chunk_size: int = Field(
        default=500,
        description="每个文本块的字符数"
    )
    chunk_overlap: int = Field(
        default=50,
        description="相邻块之间的重叠字符数"
    )
    separators: list[str] = Field(
        default=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
        description="分块分隔符（优先级从高到低）"
    )


class AppConfig(BaseModel):
    """应用总配置"""
    obsidian_path: str = Field(
        default="",
        description="Obsidian 知识库根目录路径"
    )
    books_dir: str = Field(
        default="./books",
        description="书籍文件存放目录（相对于 obsidian_path）"
    )
    chroma_dir: str = Field(
        default="./chroma_db",
        description="ChromaDB 向量数据库存储目录"
    )
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig,
        description="嵌入模型配置"
    )
    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM 配置"
    )
    chunk: ChunkConfig = Field(
        default_factory=ChunkConfig,
        description="文档分块配置"
    )
    top_k: int = Field(
        default=5,
        description="检索时返回的最相关段落数"
    )


# ============================================================
# 配置管理器
# ============================================================

class ConfigManager:
    """管理应用配置的加载、保存和验证"""

    CONFIG_DIR = Path.home() / ".deepresearch"
    CONFIG_FILE = CONFIG_DIR / "config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器。

        Args:
            config_path: 配置文件路径，默认 ~/.deepresearch/config.yaml
        """
        self.config_path = config_path or self.CONFIG_FILE
        self._config: Optional[AppConfig] = None

    # ---- 配置加载 ----

    def load(self) -> AppConfig:
        """加载并验证配置文件，不存在则返回默认配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._config = AppConfig(**data)
            except (yaml.YAMLError, ValidationError) as e:
                print(f"⚠️  配置文件解析失败，使用默认配置：{e}")
                self._config = AppConfig()
        else:
            self._config = AppConfig()
        return self._config

    def save(self, config: Optional[AppConfig] = None) -> Path:
        """保存配置到文件"""
        if config:
            self._config = config
        if self._config is None:
            self._config = AppConfig()

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 model_dump 序列化，排除 None 值
        data = self._config.model_dump(exclude_none=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return self.config_path

    @property
    def config(self) -> AppConfig:
        """获取当前配置（自动加载）"""
        if self._config is None:
            self.load()
        return self._config  # type: ignore[return-value]

    # ---- 便捷方法 ----

    def get(self, key: str) -> Any:
        """通过点号路径获取配置值，如 'llm.model'"""
        obj = self.config
        for part in key.split("."):
            obj = getattr(obj, part)
        return obj

    def set(self, key: str, value: Any) -> None:
        """通过点号路径设置配置值并保存，如 'llm.model' 'claude-opus-4-8'"""
        parts = key.split(".")
        obj = self.config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
        self.save()

    def show(self) -> str:
        """以 YAML 格式展示当前配置"""
        return yaml.dump(
            self.config.model_dump(exclude_none=True),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def init(self, obsidian_path: str) -> Path:
        """
        初始化项目：设置 Obsidian 路径并生成默认配置文件。

        Args:
            obsidian_path: Obsidian 知识库根目录

        Returns:
            配置文件路径
        """
        config = AppConfig(obsidian_path=obsidian_path)
        self.save(config)
        return self.config_path
