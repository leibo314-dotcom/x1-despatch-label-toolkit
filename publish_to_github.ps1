param(
    [string]$RepoName = "x1-despatch-label-toolkit",
    [switch]$Private
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$gitBin = "C:\Program Files\Git\bin"
$ghBin = "C:\Program Files\GitHub CLI"
$env:Path = "$gitBin;$ghBin;$env:Path"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Project root: $projectRoot"

$gitName = git -C $projectRoot config --global user.name
$gitEmail = git -C $projectRoot config --global user.email

if (-not $gitName -or -not $gitEmail) {
    throw "Git user.name or user.email is not configured yet. Run:`n  git config --global user.name ""Your Name""`n  git config --global user.email ""you@example.com"""
}

gh auth status | Out-Null

$visibility = if ($Private) { "--private" } else { "--public" }

git -C $projectRoot add .
git -C $projectRoot status --porcelain 1>$null 2>$null
$changes = git -C $projectRoot status --porcelain
if ($changes) {
    git -C $projectRoot commit -m "Initial web app for X1 despatch labels"
}

$repoExists = $false
try {
    gh repo view $RepoName | Out-Null
    $repoExists = $true
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    gh repo create $RepoName $visibility --source $projectRoot --remote origin --push
} else {
    $remoteUrl = gh repo view $RepoName --json url -q .url
    $existingRemote = git -C $projectRoot remote
    if (-not ($existingRemote -split "\r?\n" | Where-Object { $_ -eq "origin" })) {
        git -C $projectRoot remote add origin "$remoteUrl.git"
    }
    git -C $projectRoot push -u origin HEAD
}

Write-Host ""
Write-Host "GitHub publish complete."
Write-Host "Next step: import the repo into Vercel."
