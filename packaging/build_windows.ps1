# Windows 打包脚本：把 grass 打成不含模型权重的可执行程序
#
# 用法（在装了 pyinstaller 的 conda 环境里）：
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#
# 产物：dist\生草机\ 目录（内含 生草机.exe 与 _internal\），
#      以及 dist\grass-v<版本>-win64.zip。
# 模型权重不入包：运行前把 milmmt_model\（默认，也可用 m2m100_model\ 或 hymt2_model\）
# 放到 生草机.exe 同级目录，或用环境变量 GRASS_MODEL_PATH 指向模型目录。

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (& python -c "from version import __version__; print(__version__)").Trim()

python -m PyInstaller `
    --noconfirm --clean --windowed --onedir `
    --name "生草机" `
    --paths "$root" `
    --collect-all customtkinter `
    --collect-all tkinterdnd2 `
    --collect-all sentencepiece `
    --collect-submodules google.protobuf `
    --hidden-import "google.protobuf" `
    --hidden-import "transformers.models.hunyuan_v1_dense" `
    --hidden-import "transformers.models.hunyuan_v1_dense.configuration_hunyuan_v1_dense" `
    --hidden-import "transformers.models.hunyuan_v1_dense.modeling_hunyuan_v1_dense" `
    --hidden-import "transformers.models.gemma3" `
    --hidden-import "transformers.models.gemma3.configuration_gemma3" `
    --hidden-import "transformers.models.gemma3.modeling_gemma3" `
    --hidden-import "transformers.models.gemma3.tokenization_gemma3" `
    --hidden-import "transformers.models.m2m_100" `
    --hidden-import "transformers.models.m2m_100.modeling_m2m_100" `
    --hidden-import "transformers.models.m2m_100.tokenization_m2m_100" `
    --exclude-module tkinter.test `
    --exclude-module pytest `
    main.py

Copy-Item -LiteralPath (Join-Path $root '模型下载说明.txt') -Destination 'dist\生草机\' -Force

$zip = "dist\grass-v$version-win64.zip"
if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path 'dist\生草机\*' -DestinationPath $zip -CompressionLevel Optimal
Write-Output "built: $zip"
