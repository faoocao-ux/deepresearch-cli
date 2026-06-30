# 🚀 发布指引

## 第一步：在 GitHub 创建仓库

1. 打开 https://github.com/new
2. 填入以下信息：
   - **Repository name**: `deepresearch-cli`
   - **Description**: `本地 CLI 研究工具：Obsidian + 向量检索 + LLM 推理`
   - **Public** 或 **Private**（按你需求）
   - ⚠️ **不要勾选** "Add a README file"（已有）
   - ⚠️ **不要勾选** ".gitignore"（已有）
   - ⚠️ **不要勾选** "Choose a license"
3. 点击 **Create repository**

## 第二步：推送代码

创建后 GitHub 会显示一个推送到已有仓库的指引，复制那三行命令运行：

```powershell
git remote add origin https://github.com/你的用户名/deepresearch-cli.git
git branch -M master
git push -u origin master
```

## 第三步：告诉别人怎么装

推上去之后，别人安装只需一行：

```bash
pip install git+https://github.com/你的用户名/deepresearch-cli.git
```

然后就能用了：

```bash
research init --obsidian-path "G:/MyObsidianVault"
research ingest
research ask "姚期智对量子计算的主要贡献是什么？"
```

---

> 💡 如果你选了 **Private** 仓库，别人需要先被你添加为 Collaborator（在仓库 Settings → Collaborators 里加），否则装不了。
