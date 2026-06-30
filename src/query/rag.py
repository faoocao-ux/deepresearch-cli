"""
RAG 推理管道 —— 将检索增强生成的全流程串联起来。

流程：
    1. 接收用户问题
    2. 通过检索器从向量库中召回相关段落
    3. 构建包含上下文和问题的提示词
    4. 调用 LLM 生成带引用的回答
    5. 返回结构化结果
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config.manager import AppConfig
from src.query.llm import BaseLLM, create_llm
from src.query.retriever import Retriever


@dataclass
class RAGResult:
    """RAG 查询结果"""
    question: str                           # 原始问题
    answer: str                             # LLM 生成的回答
    sources: list[dict] = field(default_factory=list)   # 引用的来源段落
    model: str = ""                         # 使用的模型名
    context_chunks: int = 0                 # 使用的上下文块数


# RAG 系统提示词模板
SYSTEM_PROMPT = """你是一个知识渊博的研究助手。你的任务是根据提供的参考资料来回答用户的问题。

请严格遵循以下规则：
1. **基于资料回答**：你的回答必须基于下面提供的「参考资料」。如果资料中没有相关信息，请明确告知用户"当前知识库中没有找到相关信息"。
2. **引用来源**：在回答中引用具体的来源文件名，格式为 `【来源: xxx.md】`。
3. **保持诚实**：不要编造资料中没有的信息。如果资料只提供了部分答案，请说明哪些是资料中的内容，哪些是你不确定的。
4. **简洁清晰**：用中文回答，语言简洁明了，重点突出。"""


# 用户消息模板
USER_PROMPT_TEMPLATE = """## 参考资料

{context}

---

## 用户问题

{question}

请基于以上参考资料回答用户的问题。"""


class RAGPipeline:
    """
    RAG 推理管道 —— 检索增强生成的核心调度器。

    用法:
        pipeline = RAGPipeline(config)
        result = pipeline.ask("姚期智对量子计算的主要贡献是什么？")
        print(result.answer)
        for src in result.sources:
            print(f"  - {src['source_file']}")
    """

    def __init__(self, config: AppConfig):
        """
        Args:
            config: 应用配置
        """
        self.config = config
        self._llm: Optional[BaseLLM] = None
        self._retriever: Optional[Retriever] = None

    def _ensure_initialized(self):
        """延迟初始化 LLM 和检索器"""
        if self._llm is None:
            self._llm = create_llm(self.config)
        if self._retriever is None:
            self._retriever = Retriever(self.config)

    def ask(
        self,
        question: str,
        top_k: Optional[int] = None,
        progress_callback=None,
    ) -> RAGResult:
        """
        执行 RAG 查询：检索 + 推理。

        Args:
            question:          用户问题
            top_k:             检索段落数（默认使用配置值）
            progress_callback: 可选进度回调 fn(stage, message)

        Returns:
            RAGResult 对象，包含回答和来源引用
        """
        self._ensure_initialized()

        k = top_k or self.config.top_k

        # ---- Step 1: 检索 ----
        _report(progress_callback, "retrieve", "正在检索相关段落...")
        sources = self._retriever.search(question, top_k=k)  # type: ignore[union-attr]

        if not sources:
            return RAGResult(
                question=question,
                answer="当前向量库为空，请先运行 `research ingest` 摄取文档。",
                sources=[],
                model=self.config.llm.model,
                context_chunks=0,
            )

        _report(progress_callback, "retrieve", f"找到 {len(sources)} 个相关段落")

        # ---- Step 2: 构建提示词 ----
        _report(progress_callback, "reason", "正在调用 LLM 生成回答...")

        context_parts: list[str] = []
        for i, src in enumerate(sources):
            source_name = src.get("source_file", "未知")
            text = src.get("text", "")
            context_parts.append(f"[{i + 1}] 来源: {source_name}\n{text}")

        context = "\n\n---\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            )},
        ]

        # ---- Step 3: 调用 LLM ----
        answer = self._llm.chat(messages)  # type: ignore[union-attr]

        _report(progress_callback, "done", "回答生成完毕")

        return RAGResult(
            question=question,
            answer=answer,
            sources=sources,
            model=self.config.llm.model,
            context_chunks=len(sources),
        )

    def get_store_stats(self) -> dict:
        """获取向量库统计（供 status 命令使用）"""
        self._ensure_initialized()
        return self._retriever.get_store_stats()  # type: ignore[union-attr]


def _report(callback, stage, message):
    """内部辅助：安全调用进度回调"""
    if callback:
        try:
            callback(stage, message)
        except Exception:
            pass
