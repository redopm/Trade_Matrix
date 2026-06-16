# =====================================================
# TradeMatrix - One-Click Deploy Script
# Usage: .\deploy-to-gcp.ps1 "Your commit message"
# =====================================================

param(
    [string]$CommitMessage = "Update: deploy latest changes"
)

$ErrorActionPreference = "Stop"
$Zone = "asia-south1-c"
$VMName = "tradematrix-vm"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TradeMatrix One-Click Deploy" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Git Add, Commit, Push
Write-Host "[1/3] Pushing code to GitHub..." -ForegroundColor Yellow
git add -A
git status --short

$stagedFiles = git diff --cached --name-only
if ($stagedFiles) {
    git commit -m $CommitMessage
    git push origin main
    Write-Host "  Pushed to GitHub!" -ForegroundColor Green
} else {
    Write-Host "  No changes to commit. Deploying current HEAD..." -ForegroundColor Gray
    git push origin main 2>$null
}

# Step 2: Run deploy script on GCP VM
Write-Host ""
Write-Host "[2/3] Deploying on GCP VM..." -ForegroundColor Yellow
gcloud.cmd compute ssh $VMName --zone $Zone --command="bash /home/ikkishprep/deploy.sh"

Write-Host ""
Write-Host "[3/3] Verifying deployment..." -ForegroundColor Yellow
gcloud.cmd compute ssh $VMName --zone $Zone --command="sudo docker ps --format 'table {{.Names}}`t{{.Status}}`t{{.Ports}}'"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Deploy Successful!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
