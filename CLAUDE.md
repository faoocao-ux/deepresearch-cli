# CLAUDE.md

此文件为 Claude Code 在此仓库中工作时提供指导。

## 项目概述

**研究工具 CLI (deepresearch-cli)** — 本地 RAG 研究助手，结合 Obsidian 书籍库 + 向量检索 + LLM 推理。

## 项目结构

```
src/
├── cli/main.py           # Typer CLI 入口（init/config/ingest/ask/status）
├── config/manager.py     # Pydantic 配置管理（AppConfig + ConfigManager）
├── ingest/               # 文档摄取模块
│   ├── loader.py         #   文档加载器（.md/.txt 递归扫描）
│   ├── chunker.py        #   文本分块器（语义边界切分 + 重叠）
│   ├── embedder.py       #   嵌入模型接口（local/OpenAI/Ollama）
│   ├── vector_store.py   #   ChromaDB 向量存储封装
│   └── pipeline.py       #   摄取管道（串联以上模块）
└── query/                # 查询推理模块
    ├── llm.py            #   LLM 接口（Anthropic/OpenAI/Ollama）
    ├── retriever.py      #   向量检索器
    └── rag.py            #   RAG 推理管道
```

## 关键命令

- `research init` — 初始化配置
- `research config show/set` — 查看/修改配置
- `research ingest` — 摄取文档到向量库
- `research ask "问题"` — RAG 问答
- `research status` — 查看向量库状态

## 技术栈

- **CLI**: Typer + Rich
- **配置**: Pydantic + YAML
- **嵌入模型**: sentence-transformers (本地) / OpenAI API / Ollama
- **向量库**: ChromaDB (本地持久化)
- **LLM**: Anthropic Claude / OpenAI / Ollama

## 编码约定

- 始终用中文回复所有问题
- 所有选项都用中文显示
- 代码注释用中文
- 遵循现有代码风格：dataclass 定义数据结构，工厂函数创建实例，延迟初始化
- 配置通过 `AppConfig` 传递，避免硬编码
- 每个模块的公开 API 通过 `__init__.py` 导出
