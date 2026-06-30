# 研究工具 CLI — 快捷启动脚本
# 用法: .\run.ps1 ask "你的问题"
#       .\run.ps1 ingest
#       .\run.ps1 config show
#       .\run.ps1 status

$env:PYTHONIOENCODING = 'utf-8'
Set-Location "$PSScriptRoot"
& .\venv\Scripts\research.exe @args
