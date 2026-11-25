# Windows 打包脚本：把 grass 打成不含模型权重的可执行程序
#
# 用法（在装了 pyinstaller 的 conda 环境里）：
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#
# 产物：dist\grass\ 目录（内含 grass.exe 与 _internal\），
#      以及 dist\grass-v<版本>-win64.zip。
# 模型权重不入包：运行前把 milmmt_model\ 放到 grass.exe 同级目录，
# 或用环境变量 GRASS_MODEL_PATH 指向模型目录。
#
# 注意：exe 名必须是纯 ASCII（grass）。中文 exe 名（如 生草机.exe）在部分 Windows 11
# 机器上会让 Qt 创建窗口时直接 abort（事件日志 0xC0000409 / ucrtbase.dll），程序闪退。

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 用哪个 Python：默认 PATH 里的 python，可用 GRASS_PYTHON 指定（例如 conda 环境的解释器）
$py = if ($env:GRASS_PYTHON) { $env:GRASS_PYTHON } else { 'python' }

$version = (& $py -c "from version import __version__; print(__version__)").Trim()

& $py -m PyInstaller `
    --noconfirm --clean --windowed --onedir `
    --name grass `
    --paths "$root" `
    --collect-all sentencepiece `
    --collect-submodules google.protobuf `
    --hidden-import "google.protobuf" `
    --hidden-import "transformers.models.gemma3" `
    --hidden-import "transformers.models.gemma3.configuration_gemma3" `
    --hidden-import "transformers.models.gemma3.modeling_gemma3" `
    --hidden-import "transformers.models.gemma3.tokenization_gemma3" `
    --exclude-module tkinter `
    --exclude-module pytest `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtWebEngineQuick `
    --exclude-module PySide6.QtWebChannel `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQuickWidgets `
    --exclude-module PySide6.QtQuick3D `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.Qt3DRender `
    --exclude-module PySide6.Qt3DAnimation `
    --exclude-module PySide6.Qt3DInput `
    --exclude-module PySide6.Qt3DLogic `
    --exclude-module PySide6.Qt3DExtras `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtGraphs `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module PySide6.QtMultimediaWidgets `
    --exclude-module PySide6.QtBluetooth `
    --exclude-module PySide6.QtNfc `
    --exclude-module PySide6.QtPositioning `
    --exclude-module PySide6.QtLocation `
    --exclude-module PySide6.QtSerialPort `
    --exclude-module PySide6.QtSerialBus `
    --exclude-module PySide6.QtSensors `
    --exclude-module PySide6.QtSql `
    --exclude-module PySide6.QtTest `
    --exclude-module PySide6.QtHelp `
    --exclude-module PySide6.QtDesigner `
    --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtPdfWidgets `
    --exclude-module PySide6.QtSpatialAudio `
    --exclude-module PySide6.QtNetworkAuth `
    main.py

Copy-Item -LiteralPath (Join-Path $root '模型下载说明.txt') -Destination 'dist\grass\' -Force

$zip = "dist\grass-v$version-win64.zip"
if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path 'dist\grass\*' -DestinationPath $zip -CompressionLevel Optimal
Write-Output "built: $zip"
