"""
LLM 调用接口 —— 统一不同提供商的大语言模型调用。

支持的提供商：
    anthropic: Anthropic Claude 系列（推荐）
    openai:    OpenAI GPT 系列 + 兼容 API
    ollama:    本地 Ollama 服务

所有实现遵循统一接口：chat(messages) -> str
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLM(ABC):
    """大语言模型抽象基类"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送消息并返回模型回复。

        Args:
            messages:    消息列表，格式 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 生成温度（None 则使用默认值）
            max_tokens:  最大输出 token 数（None 则使用默认值）

        Returns:
            模型回复文本
        """
        ...


# ============================================================
# Anthropic Claude 实现
# ============================================================

class AnthropicLLM(BaseLLM):
    """
    调用 Anthropic Claude API。

    支持的模型：claude-sonnet-4-6, claude-opus-4-8, claude-haiku-4-5 等
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature
        self._client = None

    def _get_client(self):
        """延迟加载 Anthropic 客户端"""
        if self._client is not None:
            return self._client
        from anthropic import Anthropic

        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self._client = Anthropic(**kwargs)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        client = self._get_client()

        # Anthropic API 需要单独的 system 消息
        system_msg = ""
        chat_messages: list[dict[str, str]] = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg += msg["content"] + "\n"
            else:
                chat_messages.append(msg)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "messages": chat_messages,
        }
        if system_msg.strip():
            kwargs["system"] = system_msg.strip()

        response = client.messages.create(**kwargs)

        # 提取文本内容
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "".join(text_parts)


# ============================================================
# OpenAI 兼容 API 实现
# ============================================================

class OpenAILLM(BaseLLM):
    """
    调用 OpenAI 兼容的 Chat Completion API。

    适用服务：
        - OpenAI GPT-4, GPT-4o, GPT-3.5
        - DeepSeek, 通义千问 等兼容接口
        - Ollama（通过 OpenAI 兼容端点）
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature
        self._client = None

    def _get_client(self):
        """延迟加载 OpenAI 客户端"""
        if self._client is not None:
            return self._client
        from openai import OpenAI

        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
        )
        return response.choices[0].message.content or ""


# ============================================================
# 工厂函数
# ============================================================

def create_llm(config) -> BaseLLM:
    """
    根据配置创建 LLM 实例。

    Args:
        config: AppConfig 对象（来自 src.config.manager）

    Returns:
        BaseLLM 实例
    """
    provider = config.llm.provider
    model = config.llm.model
    api_key = config.llm.api_key
    base_url = config.llm.base_url
    max_tokens = config.llm.max_tokens
    temperature = config.llm.temperature

    if provider == "anthropic":
        return AnthropicLLM(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    elif provider == "openai":
        return OpenAILLM(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    elif provider == "ollama":
        # Ollama 走 OpenAI 兼容协议
        ollama_url = base_url or "http://localhost:11434/v1"
        return OpenAILLM(
            model=model,
            base_url=ollama_url,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
