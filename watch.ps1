# ============================================================
# 自动监听导入脚本 — 把书放入 drop/ 目录，自动转换 + 摄取
# ============================================================
# 用法: .\watch.ps1
#       放入文件到 drop/ 目录，自动检测并处理
#       Ctrl+C 停止监听
# ============================================================

param(
    [string]$WatchDir = ".\drop"
)

$env:PYTHONIOENCODING = 'utf-8'
Set-Location "$PSScriptRoot"

# 确保 drop 目录存在
if (-not (Test-Path $WatchDir)) {
    New-Item -ItemType Directory -Path $WatchDir | Out-Null
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 📂 正在监听: $((Resolve-Path $WatchDir).Path)" -ForegroundColor Cyan
Write-Host "   把书籍文件拖入这个文件夹，自动转换并导入" -ForegroundColor DarkGray
Write-Host "   支持: PDF / EPUB / DOCX / HTML / MD / TXT" -ForegroundColor DarkGray
Write-Host "   Ctrl+C 停止" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# FileSystemWatcher
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = (Resolve-Path $WatchDir).Path
$watcher.Filter = "*.*"
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

# 防抖：同一个文件可能触发多次事件
$pending = @{}

$action = {
    $path = $Event.SourceEventArgs.FullPath
    $name = $Event.SourceEventArgs.Name
    $changeType = $Event.SourceEventArgs.ChangeType

    # 只处理 Created / Changed
    if ($changeType -notin 'Created', 'Changed') { return }

    # 跳过隐藏文件、临时文件
    if ($name.StartsWith('.') -or $name.StartsWith('~') -or $name.EndsWith('.tmp')) { return }

    # 防抖：3 秒内的重复事件忽略
    if ($pending.ContainsKey($path)) {
        $elapsed = (Get-Date) - $pending[$path]
        if ($elapsed.TotalSeconds -lt 5) { return }
    }
    $pending[$path] = Get-Date

    # 检查文件是否稳定（不再被写入）
    Start-Sleep -Seconds 2
    try {
        $file = Get-Item $path -ErrorAction Stop
        $size1 = $file.Length
        Start-Sleep -Seconds 1
        $file.Refresh()
        $size2 = $file.Length
        if ($size1 -ne $size2) { return }  # 文件还在写入中
    } catch {
        return
    }

    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 检测到新文件: $name" -ForegroundColor Yellow

    # 调用 research add
    $result = & .\venv\Scripts\research.exe add $path 2>&1
    Write-Host $result

    # 处理完后移动到 done/
    $doneDir = Join-Path $WatchDir "done"
    if (-not (Test-Path $doneDir)) {
        New-Item -ItemType Directory -Path $doneDir | Out-Null
    }
    $dest = Join-Path $doneDir $name
    $counter = 1
    while (Test-Path $dest) {
        $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
        $ext = [System.IO.Path]::GetExtension($name)
        $dest = Join-Path $doneDir "$($base)_$counter$ext"
        $counter++
    }
    Move-Item $path $dest -Force
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 处理完毕 → done/" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host ""
}

$handlers = @()
$handlers += Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action
$handlers += Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action

Write-Host " 等待文件放入..." -ForegroundColor DarkGray
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($h in $handlers) {
        Unregister-Event -SubscriptionId $h.Id -ErrorAction SilentlyContinue
    }
    $watcher.Dispose()
    Write-Host "监听已停止" -ForegroundColor Yellow
}
