param(
    [string]$SourceRoot = "C:\Users\jerem\Repos\pers\ha-mcp-test\ha-mcp-bridge-addon",
    [string]$TargetRoot = "C:\Users\jerem\Repos\pers\ha-mcp-conv-bridge"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Copy-RequiredFile {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "Required file missing: $SourcePath"
    }

    $targetDir = Split-Path -Parent $TargetPath
    if (-not (Test-Path -LiteralPath $targetDir -PathType Container)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force
}

function Copy-RequiredDirectory {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        throw "Required directory missing: $SourcePath"
    }

    if (Test-Path -LiteralPath $TargetPath) {
        Remove-Item -LiteralPath $TargetPath -Recurse -Force
    }

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    Copy-Item -Path (Join-Path $SourcePath '*') -Destination $TargetPath -Recurse -Force
}

$sourceRootResolved = (Resolve-Path -LiteralPath $SourceRoot).Path
if (-not (Test-Path -LiteralPath $TargetRoot -PathType Container)) {
    throw "Target root not found: $TargetRoot"
}
$targetRootResolved = (Resolve-Path -LiteralPath $TargetRoot).Path

Write-Host "Sync source: $sourceRootResolved"
Write-Host "Sync target: $targetRootResolved"

$rootFiles = @(
    "README.md",
    "repository.yaml",
    "voice-assist-instructions.md"
)

foreach ($file in $rootFiles) {
    Copy-RequiredFile -SourcePath (Join-Path $sourceRootResolved $file) -TargetPath (Join-Path $targetRootResolved $file)
    Write-Host "Copied file: $file"
}

Copy-RequiredDirectory -SourcePath (Join-Path $sourceRootResolved "mcp_conversation_bridge") -TargetPath (Join-Path $targetRootResolved "mcp_conversation_bridge")
Write-Host "Copied directory: mcp_conversation_bridge"

Write-Host "Sync complete."
