param(
    [string]$Python = "python"
)

# Builds from an ordinary PowerShell session after installing Visual Studio Build Tools.
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) { throw "Visual Studio Build Tools was not found." }
$install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $install) { throw "Install the C++ workload: Microsoft.VisualStudio.Workload.VCTools" }
$vcvars = Join-Path $install "VC\Auxiliary\Build\vcvars64.bat"
$sdkRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\Include"
$sdk = Get-ChildItem $sdkRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
if (-not $sdk) { throw "Windows 10/11 SDK headers were not found." }

# pyconfig.h needs the SDK shared and UM headers. vcvars supplies compiler and linker paths.
$command = "call `"$vcvars`" && set `"INCLUDE=%INCLUDE%;$($sdk.FullName)\shared;$($sdk.FullName)\um`" && `"$Python`" setup.py build_ext --inplace"
& cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
