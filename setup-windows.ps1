$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Check = Join-Path $Root "scripts\prerequisites.py"

function Stop-Setup($Message) {
    Write-Host "`nSetup failed: $Message" -ForegroundColor Red
    exit 1
}

function Refresh-Path {
    $Machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $User = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$Machine;$User"
}

function Find-Python {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) {
        foreach ($Version in @("3.11", "3.12", "3.10")) {
            & $Launcher.Source "-$Version" $Check python *> $null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{ Command = $Launcher.Source; Prefix = "-$Version"; Version = $Version }
            }
        }
    }
    $Interpreter = Get-Command python -ErrorAction SilentlyContinue
    if ($Interpreter) {
        & $Interpreter.Source $Check python *> $null
        if ($LASTEXITCODE -eq 0) {
            $Version = (& $Interpreter.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            return [pscustomobject]@{ Command = $Interpreter.Source; Prefix = ""; Version = $Version }
        }
    }
    return $null
}

function Find-Node {
    $Node = Get-Command node -ErrorAction SilentlyContinue
    $Npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $Node -or -not $Npm) { return $false }
    $Version = (& node --version 2>$null)
    if ($Version -match '^v?(22|24)\.(\d+)\.\d+') {
        return [int]$Matches[1] -eq 24 -or [int]$Matches[2] -ge 12
    }
    return $false
}

function Invoke-Python($Python, [string[]]$Arguments) {
    if ($Python.Prefix) {
        & $Python.Command $Python.Prefix @Arguments | Out-Host
    } else {
        & $Python.Command @Arguments | Out-Host
    }
    return $LASTEXITCODE
}

function Install-Prerequisites($NeedPython, $NeedNode) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        if ($NeedPython) { Start-Process "https://www.python.org/downloads/windows/" }
        if ($NeedNode) { Start-Process "https://nodejs.org/en/download" }
        Stop-Setup "winget is not available. Install the missing prerequisites from the official pages opened above, then run setup again."
    }
    Write-Host "`nMissing prerequisites can be installed for your Windows user with winget." -ForegroundColor Yellow
    if ($NeedPython) { Write-Host "  Python 3.11 x64 (Python.Python.3.11)" }
    if ($NeedNode) { Write-Host "  Node.js LTS x64 (OpenJS.NodeJS.LTS)" }
    $Answer = Read-Host "Install the missing prerequisites now? [y/N]"
    if ($Answer -notin @("y", "Y")) {
        if ($NeedPython) { Start-Process "https://www.python.org/downloads/windows/" }
        if ($NeedNode) { Start-Process "https://nodejs.org/en/download" }
        Stop-Setup "Install the prerequisites from the official pages and run setup again."
    }
    if ($NeedPython) {
        & winget install --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Stop-Setup "winget could not install Python. Use https://www.python.org/downloads/windows/ and rerun setup." }
    }
    if ($NeedNode) {
        & winget install --id OpenJS.NodeJS.LTS --scope user --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Stop-Setup "winget could not install Node.js. Use https://nodejs.org/en/download and rerun setup." }
    }
    Refresh-Path
}

Write-Host "WakeUp2 setup for Windows 10/11"
$Architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
if ($Architecture -ne "X64") { Stop-Setup "This setup supports Windows x64 only. Detected $Architecture." }

$Python = Find-Python
$NodeAvailable = Find-Node
if (-not $Python -or -not $NodeAvailable) {
    Install-Prerequisites (-not $Python) (-not $NodeAvailable)
    $Python = Find-Python
    $NodeAvailable = Find-Node
}
if (-not $Python) { Stop-Setup "Python 3.10, 3.11, or 3.12 was not found. Restart this script after installing Python." }
if (-not $NodeAvailable) { Stop-Setup "Node.js 22.12+ or 24.x was not found. Restart this script after installing Node.js." }

$PythonExit = Invoke-Python $Python @($Check, "host")
if ($PythonExit -ne 0) { Stop-Setup "Unsupported Windows platform." }
$PythonExit = Invoke-Python $Python @($Check, "python")
if ($PythonExit -ne 0) { Stop-Setup "The selected Python version is unsupported." }
Write-Host "`nUsing Python $($Python.Version) and Node.js $(& node --version)."

$Venv = Join-Path $Root "venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (Test-Path $Venv) {
    if (-not (Test-Path $VenvPython)) { Stop-Setup "An existing venv is incomplete. Back it up and rename it manually; setup will not delete it." }
    & $VenvPython $Check python
    if ($LASTEXITCODE -ne 0) { Stop-Setup "The existing venv uses an unsupported Python. Back it up and rename it manually; setup will not delete it." }
} else {
    Write-Host "`nCreating WakeUp2 environment..."
    $PythonExit = Invoke-Python $Python @("-m", "venv", $Venv)
    if ($PythonExit -ne 0) { Stop-Setup "Could not create the local Python environment." }
}

Write-Host "`nInstalling application dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-Setup "Could not update pip inside the project environment." }
& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-Setup "Python dependencies could not be installed. Review the error above." }
$PipCheck = & $VenvPython -m pip check 2>&1
if ($LASTEXITCODE -ne 0) {
    if (($PipCheck -join "`n").Trim() -eq "mediapipe 0.10.21 is not supported on this platform") {
        Write-Host "Checking MediaPipe runtime compatibility (the wheel metadata is flagged by pip check)..."
        & $VenvPython -c "import cv2, mediapipe; from mediapipe.python import solutions; assert hasattr(solutions, 'face_mesh'); print('MediaPipe and OpenCV runtime imports are ready.')"
        if ($LASTEXITCODE -ne 0) { Stop-Setup "MediaPipe is not usable on this Windows computer." }
    } else {
        $PipCheck | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Stop-Setup "Python dependency versions conflict."
    }
}

Write-Host "`nInstalling frontend dependencies..."
Push-Location (Join-Path $Root "frontend")
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Frontend dependencies could not be installed." }
    Write-Host "`nBuilding the frontend..."
    & npm run build
    if ($LASTEXITCODE -ne 0) { Stop-Setup "The frontend build failed. Review the output above." }
} finally {
    Pop-Location
}

Write-Host "`nValidating WakeUp2..."
& $VenvPython -c "import cv2, mediapipe, fastapi; print('Python imports are ready.')"
if ($LASTEXITCODE -ne 0) { Stop-Setup "A required backend import failed." }
if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) { Stop-Setup "The frontend build output is missing." }
New-Item -ItemType Directory -Force -Path (Join-Path $Root "data-local") | Out-Null
Write-Host "`nSetup completed successfully." -ForegroundColor Green
Write-Host "Run start-windows.bat to launch WakeUp2 in your browser."
Write-Host "Allow camera access to the application when Windows asks."
