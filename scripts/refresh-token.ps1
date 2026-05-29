<#
.SYNOPSIS
    Refresh the Gmail OAuth token and redeploy it to the live EC2 bot.

.DESCRIPTION
    The Google "Testing" OAuth app revokes refresh tokens after ~7 days of
    issuance. This script runs the full recovery loop end-to-end so it can be
    invoked as a one-shot pre-flight before Demo Day:

      1. Delete the stale local token.pickle.
      2. Re-run the local OAuth browser consent flow (writes a fresh token.pickle).
      3. Base64-encode the fresh token.
      4. Send via AWS SSM aws-runShellScript to the instance: decode -> atomic
         move into /home/copilot/email-assistant/token.pickle -> restart copilot.
      5. Smoke-check /health on the public URL.

    Run from the repo root with the project venv present.

.PARAMETER InstanceId
    EC2 instance id to deploy to. Defaults to the production copilot instance.

.PARAMETER Region
    AWS region for SSM + EC2 calls.

.PARAMETER HealthUrl
    Public /health endpoint to smoke-check after restart.

.EXAMPLE
    .\scripts\refresh-token.ps1
#>
[CmdletBinding()]
param(
    [string]$InstanceId = "i-0ac257c4dc01e804f",
    [string]$Region     = "eu-west-1",
    [string]$HealthUrl  = "https://79-125-102-15.nip.io/health"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host ">>> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# -- Pre-flight ---------------------------------------------------------------

Step "Pre-flight checks"
if (-not (Test-Path "app") -or -not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run this from the repo root with the .venv created (couldn't find app/ or .venv\Scripts\python.exe)."
}
$caller = aws sts get-caller-identity --output text 2>$null
if (-not $caller) { throw "AWS CLI is not authenticated. Run 'aws configure' or set AWS_PROFILE first." }
Ok "AWS identity: $($caller -split '\s+' | Select-Object -First 1)"

# -- Step 1: re-auth locally --------------------------------------------------

Step "Re-authenticating Gmail OAuth (browser will open)"
if (Test-Path token.pickle) {
    Remove-Item token.pickle -Force
    Ok "Removed stale token.pickle"
}
.venv\Scripts\python -c "from app.gmail.auth import get_credentials; get_credentials()"
if (-not (Test-Path token.pickle)) { throw "OAuth flow did not write a token.pickle. Aborting." }
$tokenInfo = Get-Item token.pickle
Ok "Fresh token.pickle written ($($tokenInfo.Length) bytes, $($tokenInfo.LastWriteTime))"

# -- Step 2: base64-encode + build SSM parameters -----------------------------

Step "Building SSM payload"
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("token.pickle"))
$remote = @"
set -e
TMP=`$(mktemp)
cat > `$TMP <<'B64EOF'
$b64
B64EOF
base64 -d `$TMP > /home/copilot/email-assistant/token.pickle.new
rm `$TMP
chown copilot:copilot /home/copilot/email-assistant/token.pickle.new
chmod 600 /home/copilot/email-assistant/token.pickle.new
mv /home/copilot/email-assistant/token.pickle.new /home/copilot/email-assistant/token.pickle
systemctl restart copilot
echo "TOKEN_DEPLOYED_AND_RESTARTED"
"@
$paramsJson = @{ commands = @($remote) } | ConvertTo-Json -Depth 5 -Compress
$paramsPath = Join-Path $env:TEMP "ssm-refresh-token-$(Get-Random).json"
$paramsJson | Set-Content -Path $paramsPath -Encoding UTF8 -NoNewline
Ok "Payload ready (base64=$($b64.Length) chars, params file=$paramsPath)"

# -- Step 3: send via SSM + poll ---------------------------------------------

Step "Sending SSM command"
try {
    $cmdId = aws ssm send-command --region $Region `
        --instance-ids $InstanceId `
        --document-name AWS-RunShellScript `
        --comment "Refresh token.pickle + restart copilot (scripts/refresh-token.ps1)" `
        --parameters "file://$paramsPath" `
        --query Command.CommandId --output text
    Ok "CommandId: $cmdId"

    $status = "Pending"
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 3
        $status = aws ssm get-command-invocation --region $Region `
            --command-id $cmdId --instance-id $InstanceId `
            --query Status --output text
        Write-Host "    [$i/10] Status: $status"
        if ($status -in @("Success","Failed","Cancelled","TimedOut")) { break }
    }

    if ($status -ne "Success") {
        Warn "Command did not reach Success. Dumping stdout + stderr from instance:"
        Write-Host "--- stdout ---"
        aws ssm get-command-invocation --region $Region --command-id $cmdId --instance-id $InstanceId --query StandardOutputContent --output text
        Write-Host "--- stderr ---"
        aws ssm get-command-invocation --region $Region --command-id $cmdId --instance-id $InstanceId --query StandardErrorContent --output text
        throw "SSM command ended in '$status'. If it's the empty-stderr 1-second 'Failed' signature, reboot the instance (see project memory) and re-run this script."
    }

    $out = aws ssm get-command-invocation --region $Region --command-id $cmdId --instance-id $InstanceId --query StandardOutputContent --output text
    if ($out -notmatch "TOKEN_DEPLOYED_AND_RESTARTED") {
        Warn "Success status but missing OK marker in stdout. Full output:"
        Write-Host $out
        throw "Aborting before smoke-check."
    }
    Ok "Token deployed + copilot restarted on $InstanceId"
}
finally {
    Remove-Item $paramsPath -ErrorAction SilentlyContinue
}

# -- Step 4: smoke-check /health ---------------------------------------------

Step "Smoke-checking $HealthUrl"
$healthy = $false
for ($i = 1; $i -le 6; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
        if ($resp.StatusCode -eq 200 -and $resp.Content -match '"ok"\s*:\s*true') {
            Ok "/health -> 200 $($resp.Content)"
            $healthy = $true
            break
        }
    } catch {
        Write-Host "    [$i/6] still waiting for /health ($($_.Exception.Message))"
        Start-Sleep -Seconds 5
    }
}
if (-not $healthy) { throw "Bot did not return a healthy /health after 30s. Check journalctl -u copilot on the instance." }

Write-Host ""
Write-Host "DONE." -ForegroundColor Green
Write-Host "Next: send /unread in Telegram to confirm Gmail end-to-end." -ForegroundColor Green