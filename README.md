# 📚 研究工具 CLI (deepresearch-cli)

本地 RAG 研究助手 —— 结合 **Obsidian 书籍库** + **向量检索** + **LLM 推理**。

## 快速开始

```bash
# 1. 安装
pip install -e .

# 2. 初始化（设置你的 Obsidian 路径）
research init --obsidian-path "G:/MyObsidianVault"

# 3. 摄取书籍到向量库
research ingest

# 4. 提问
research ask "姚期智对量子计算的主要贡献是什么？"
```

## 命令一览

| 命令 | 说明 | 状态 |
|------|------|------|
| `research init` | 初始化项目配置 | ✅ 已实现 |
| `research config show` | 查看当前配置 | ✅ 已实现 |
| `research config set` | 修改配置项 | ✅ 已实现 |
| `research ingest` | 摄取文档到向量库 | ✅ 已实现 |
| `research ask` | 向知识库提问 | ✅ 已实现 |
| `research status` | 查看索引进度 | ✅ 已实现 |

## 项目结构

```
研究工具-cli/
├── pyproject.toml          # 项目元数据
├── requirements.txt        # 依赖清单
├── config_template.yaml    # 配置模板
├── PROJECT_PROGRESS.md     # 📊 项目进度表
├── README.md               # 使用文档
├── books/                  # 书籍存放目录
├── tests/                  # 测试目录
└── src/
    ├── cli/main.py         # CLI 入口
    ├── config/manager.py   # 配置管理器
    ├── ingest/             # 文档摄取模块（第2块）
    └── query/              # 查询推理模块（第3块）
```
