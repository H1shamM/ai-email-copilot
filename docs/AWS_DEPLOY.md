# AWS Deployment Runbook

Single-instance deployment of AI Email Copilot to AWS EC2 with HTTPS via Let's Encrypt and a stable hostname (`<dashed-ip>.nip.io`). Closes Week 6 Story A (#28).

**Topology**: one `t4g.nano` instance in `eu-west-1`, Elastic IP, Caddy reverse proxy on 443, FastAPI/uvicorn on 127.0.0.1:8000 under `systemd`. No SSH — shell access is via AWS Systems Manager Session Manager.

**Prerequisites**:

- AWS account with a billing alarm set (see Step 0).
- AWS CLI v2 installed locally and authenticated (`aws sts get-caller-identity` works).
- Session Manager Plugin for AWS CLI ([install docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)).
- The repo cloned locally with a working `token.pickle` (you ran the bot at least once).
- Telegram bot token + chat id ready (same values as your local `.env`).

> All commands assume `eu-west-1`. If you change region, also change every `--region` flag below.

---

## Step 0 — One-time account hygiene

**Set a billing alarm.** Don't skip this — a runaway loop on Anthropic could outpace EC2's cost by 100×.

1. Console → CloudWatch → Alarms → **Billing** (must be in `us-east-1` to view this).
2. Create alarm at total estimated charges > **USD 20** → SNS topic → your email → Confirm.

---

## Step 1 — Pick a key set of variables

Set these in your shell (PowerShell). They're referenced by the rest of the runbook.

```powershell
$env:AWS_REGION = "eu-west-1"
$env:INSTANCE_NAME = "email-copilot"
$env:IAM_ROLE_NAME = "copilot-ssm"
$env:IAM_PROFILE_NAME = "copilot-ssm"
$env:SG_NAME = "copilot-sg"
$env:SG_DESC = "AI Email Copilot - 443 in, SSM for shell"  # ASCII only — AWS rejects non-ASCII in SG descriptions
$env:EIP_TAG = "copilot-eip"
$env:S3_BOOTSTRAP_BUCKET = "copilot-bootstrap-$(Get-Random -Minimum 100000 -Maximum 999999)"
```

---

## Step 2 — IAM instance profile (for SSM)

```powershell
aws iam create-role --role-name $env:IAM_ROLE_NAME `
  --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"ec2.amazonaws.com\"},\"Action\":\"sts:AssumeRole\"}]}'

aws iam attach-role-policy --role-name $env:IAM_ROLE_NAME `
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

aws iam create-instance-profile --instance-profile-name $env:IAM_PROFILE_NAME

aws iam add-role-to-instance-profile `
  --instance-profile-name $env:IAM_PROFILE_NAME `
  --role-name $env:IAM_ROLE_NAME
```

> Wait ~10 seconds — IAM eventual consistency. The `RunInstances` call below will fail with `InvalidParameterValue` if the profile isn't propagated yet.

---

## Step 3 — Security group

```powershell
$VPC_ID = aws ec2 describe-vpcs --region $env:AWS_REGION `
  --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text

$SG_ID = aws ec2 create-security-group --region $env:AWS_REGION `
  --group-name $env:SG_NAME --description $env:SG_DESC `
  --vpc-id $VPC_ID --query "GroupId" --output text

aws ec2 authorize-security-group-ingress --region $env:AWS_REGION `
  --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0

# Default egress (all out) is fine. NO ingress on 22 — SSM replaces SSH.
```

---

## Step 4 — Find the latest Ubuntu 24.04 LTS arm64 AMI

```powershell
$AMI_ID = aws ec2 describe-images --region $env:AWS_REGION `
  --owners 099720109477 `
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*" `
            "Name=state,Values=available" `
  --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text

Write-Host "Using AMI $AMI_ID"
```

---

## Step 5 — Launch the instance

```powershell
$INSTANCE_ID = aws ec2 run-instances --region $env:AWS_REGION `
  --image-id $AMI_ID --instance-type t4g.nano `
  --security-group-ids $SG_ID `
  --iam-instance-profile "Name=$env:IAM_PROFILE_NAME" `
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$env:INSTANCE_NAME}]" `
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled" `
  --query "Instances[0].InstanceId" --output text

Write-Host "Launched $INSTANCE_ID — waiting for it to reach 'running'…"

aws ec2 wait instance-running --region $env:AWS_REGION --instance-ids $INSTANCE_ID
```

`metadata-options HttpTokens=required` enables IMDSv2 only — small but free hardening win.

---

## Step 6 — Allocate + associate Elastic IP

```powershell
$EIP_ALLOC = aws ec2 allocate-address --region $env:AWS_REGION `
  --domain vpc `
  --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$env:EIP_TAG}]" `
  --query "AllocationId" --output text

$EIP = aws ec2 describe-addresses --region $env:AWS_REGION `
  --allocation-ids $EIP_ALLOC --query "Addresses[0].PublicIp" --output text

aws ec2 associate-address --region $env:AWS_REGION `
  --instance-id $INSTANCE_ID --allocation-id $EIP_ALLOC | Out-Null

$EIP_DASHED = $EIP.Replace(".", "-")
Write-Host "Public hostname: https://$EIP_DASHED.nip.io"
```

---

## Step 7 — Open an SSM session

Wait ~60 seconds after launch for the SSM agent to register. Then:

```powershell
aws ssm start-session --region $env:AWS_REGION --target $INSTANCE_ID
```

Everything below runs **inside the SSM session**, on the instance.

---

## Step 8 — System bootstrap (on the instance)

```bash
sudo -i

# Install OS deps
apt-get update
apt-get install -y python3.12-venv python3-pip git curl debian-keyring debian-archive-keyring apt-transport-https
# Caddy from official repo (NOT snap — snap version is awful on EC2)
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

# Service user — no shell login, no home crypto, just runs the bot.
adduser --system --group --shell /bin/bash --home /home/copilot copilot
mkdir -p /home/copilot
chown copilot:copilot /home/copilot

# Clone the repo as copilot (replace with your fork URL if different)
sudo -u copilot git clone https://github.com/H1shamM/ai-email-copilot.git /home/copilot/email-assistant

# Python venv + deps
sudo -u copilot bash -c '
  cd /home/copilot/email-assistant
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
'
```

---

## Step 9 — Bootstrap `.env` (on the instance)

```bash
sudo -u copilot cp /home/copilot/email-assistant/.env.example /home/copilot/email-assistant/.env
sudo -u copilot chmod 600 /home/copilot/email-assistant/.env

# Edit it — paste real values:
nano /home/copilot/email-assistant/.env
```

Set every key from `.env.example`. Critically:

- `TELEGRAM_WEBHOOK_URL=https://<EIP_DASHED>.nip.io/telegram/webhook` (replace `<EIP_DASHED>` with the dashed form of your EIP from Step 6).
- `TELEGRAM_PUSH_INTERVAL_MINUTES=5` (or whatever cadence you want).
- All other keys identical to your local `.env`.

---

## Step 10 — Bootstrap `token.pickle` via S3 (laptop ⇄ S3 ⇄ instance)

**On your laptop** (PowerShell, in the repo root):

```powershell
# Make sure token.pickle is fresh — re-auth if needed:
.venv\Scripts\python -c "from app.gmail.auth import get_credentials; get_credentials()"

# Create a temporary bucket and upload
aws s3api create-bucket --region $env:AWS_REGION `
  --bucket $env:S3_BOOTSTRAP_BUCKET `
  --create-bucket-configuration "LocationConstraint=$env:AWS_REGION"

aws s3 cp token.pickle s3://$env:S3_BOOTSTRAP_BUCKET/token.pickle
```

**On the instance** (in the SSM session as root):

```bash
# Replace BUCKET with the value of $env:S3_BOOTSTRAP_BUCKET printed by `echo $env:S3_BOOTSTRAP_BUCKET` on the laptop.
BUCKET="copilot-bootstrap-XXXXXX"

# The instance role doesn't have S3 access yet — give it a temporary read.
# Easier path: presigned URL from the laptop. From the laptop:
#   aws s3 presign s3://$env:S3_BOOTSTRAP_BUCKET/token.pickle --expires-in 600
# Copy the URL it prints, then on the instance:

curl -o /home/copilot/email-assistant/token.pickle "<presigned-url-here>"
chown copilot:copilot /home/copilot/email-assistant/token.pickle
chmod 600 /home/copilot/email-assistant/token.pickle
```

**Back on the laptop — clean up the bucket immediately**:

```powershell
aws s3 rm s3://$env:S3_BOOTSTRAP_BUCKET/token.pickle
aws s3api delete-bucket --bucket $env:S3_BOOTSTRAP_BUCKET --region $env:AWS_REGION
```

---

## Step 11 — Caddy reverse proxy (on the instance)

The instance reads its own EIP from IMDSv2, so there's nothing to type by hand:

```bash
# 1. Pull the public IP from the instance metadata service.
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
EIP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4)
EIP_DASHED=${EIP//./-}
echo "EIP=$EIP  hostname=$EIP_DASHED.nip.io"

# 2. Generate the real Caddyfile from the template (no manual editing).
sed "s/<EIP_DASHED>/$EIP_DASHED/" /home/copilot/email-assistant/infra/Caddyfile.template \
  > /etc/caddy/Caddyfile

# 3. Confirm the placeholder was replaced before reloading.
grep -E "sslip\.io" /etc/caddy/Caddyfile
# Must print: <real-dashed-ip>.nip.io {  — NOT <EIP_DASHED>.nip.io

mkdir -p /var/log/caddy
chown caddy:caddy /var/log/caddy

systemctl reload caddy
journalctl -u caddy -n 30 --no-pager
```

You should see Caddy pulling a Let's Encrypt cert within ~10 seconds (`certificate obtained successfully`). If you see ACME errors, check that 443 is reachable from the public internet:
```bash
curl -v https://$EIP_DASHED.nip.io/  # should at least connect (200 from the bot or 502 from caddy)
```

> **Don't manually edit `/etc/caddy/Caddyfile`** — `<EIP_DASHED>` is the only value that needs substitution and the IMDS-driven `sed` above does it deterministically. Hand-editing risks the exact failure caught during W6-A's first deploy: the placeholder leaked through unchanged and Caddy refused to load.

---

## Step 12 — systemd unit for the bot (on the instance)

```bash
cp /home/copilot/email-assistant/infra/copilot.service /etc/systemd/system/copilot.service
systemctl daemon-reload
systemctl enable --now copilot
sleep 3
systemctl status copilot --no-pager
journalctl -u copilot -n 30 --no-pager
```

Look for:
- `Active: active (running)`
- `Telegram webhook registered at https://...`
- `Push scheduler started (interval=5m, threshold=4)`

---

## Step 13 — Smoke test

**From your laptop**:

```powershell
# 1. /health endpoint
curl https://$EIP_DASHED.nip.io/health
# Expected: {"ok":true}

# 2. Telegram webhook
curl "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/getWebhookInfo"
# Expected: url matches your nip.io URL, last_error_message is empty
```

**In Telegram**:

- Send `/start` — bot responds with welcome.
- Send `/unread` — fetches Gmail.
- Send `/analyze` then `/inbox` — drafts via Claude, lists with `#id` prefixes.
- Send `/reply <id>` — 3 drafts appear with the action keyboard.
- Wait ~5 min for a high-priority email to trigger a push notification.

**Reboot test**:

```powershell
aws ec2 reboot-instances --region $env:AWS_REGION --instance-ids $INSTANCE_ID
# Wait ~90s, then re-run the smoke test. systemd should have restarted both caddy and copilot.
```

---

## Step 14 — Update local docs

Once the deploy is live, on your laptop:

1. Mark Story W6-A complete in `docs/PROGRESS.md`.
2. Comment on issue #28 with the live URL and any deviations from this runbook.

---

## CI/CD: GitHub Actions auto-deploy (W6-B)

Once Story A is live, this section sets up auto-deploy on every push to `main`. The workflow file is `.github/workflows/deploy.yml` — it uses **OIDC** (no long-lived AWS access keys) to assume an IAM role that's allowed to send a deploy command via SSM to the one instance, then smoke-checks `/health` to verify.

### Step CD-1 — Create the GitHub OIDC identity provider in IAM

Run on your **laptop** (one-time per AWS account):

```powershell
aws iam create-open-id-connect-provider `
  --url https://token.actions.githubusercontent.com `
  --client-id-list sts.amazonaws.com `
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

> The thumbprint is GitHub's well-known cert thumbprint. AWS verifies the OIDC JWT against this; the OIDC token is short-lived (15 min) and per-workflow-run, so even if intercepted there's nothing to steal long-term. AWS now also supports `--thumbprint-list` being optional (auto-fetched), but pinning it is the canonical pattern.

If the provider already exists in your account from another repo, this returns `EntityAlreadyExistsException` — that's fine, skip to CD-2.

### Step CD-2 — Capture the AWS account ID

```powershell
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
Write-Host "ACCOUNT_ID=$ACCOUNT_ID"
```

### Step CD-3 — Trust policy (who can assume the role)

Replace `H1shamM/ai-email-copilot` with your actual fork if different. The `:sub` condition restricts assumption to commits on this repo's `main` branch — a fork can't get into your AWS account.

```powershell
@"
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:H1shamM/ai-email-copilot:ref:refs/heads/main"
      }
    }
  }]
}
"@ | Out-File -FilePath trust-policy.json -Encoding ascii
```

### Step CD-4 — Permission policy (what the role can do)

Scoped to one SSM action on one instance + one document. Anything more is unnecessary.

```powershell
@"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DeployViaSSMSendCommand",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:$($env:AWS_REGION):$($ACCOUNT_ID):instance/$INSTANCE_ID",
        "arn:aws:ssm:$($env:AWS_REGION)::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ReadCommandStatus",
      "Effect": "Allow",
      "Action": "ssm:GetCommandInvocation",
      "Resource": "*"
    }
  ]
}
"@ | Out-File -FilePath deploy-policy.json -Encoding ascii
```

### Step CD-5 — Create the role and attach the policy

```powershell
$ROLE_ARN = aws iam create-role `
  --role-name copilot-github-deploy `
  --assume-role-policy-document file://trust-policy.json `
  --description "GitHub Actions deploys to the AI Email Copilot EC2 instance via SSM" `
  --query "Role.Arn" --output text

aws iam put-role-policy `
  --role-name copilot-github-deploy `
  --policy-name copilot-github-deploy-inline `
  --policy-document file://deploy-policy.json

Write-Host "ROLE_ARN=$ROLE_ARN"

# Clean up local files (the policies are now in IAM)
Remove-Item trust-policy.json, deploy-policy.json
```

### Step CD-6 — Add repo secrets

```powershell
gh secret set AWS_DEPLOY_ROLE_ARN --body "$ROLE_ARN"
gh secret set AWS_INSTANCE_ID --body "$INSTANCE_ID"
```

(Or via the GitHub web UI: *Settings → Secrets and variables → Actions → New repository secret*.)

### Step CD-7 — Trigger a deploy

The workflow already exists at `.github/workflows/deploy.yml` after PR for #30 merges. To trigger:

- **Automatic:** any subsequent push to `main` runs it.
- **Manual:** `gh workflow run deploy.yml` (or the Actions UI's *Run workflow* button).

Watch it: `gh run watch` or the Actions tab. A successful run logs:

```
Configure AWS credentials via OIDC ... ok
Send deploy command via SSM ... command_id=...
Wait for SSM command ... [1/30] Status: Success
Smoke-check /health ... {"ok":true}
```

### Step CD-8 — Rollback

GitHub Actions UI → **Actions** tab → pick a previous successful **Deploy** run → **Re-run all jobs**. The re-run inherits that run's `github.sha`, so the deploy script checks out the older commit and restarts the bot. No git surgery on the instance.

If the bad commit is already on `main`, you can also revert via PR (`git revert <sha> && open PR`) — the merge of that revert auto-deploys via the normal workflow.

---

## Teardown (when you want to stop paying)

```powershell
# Run on your laptop, AFTER reading the rest of this section.

# 1. Stop the instance
aws ec2 terminate-instances --region $env:AWS_REGION --instance-ids $INSTANCE_ID
aws ec2 wait instance-terminated --region $env:AWS_REGION --instance-ids $INSTANCE_ID

# 2. Release the EIP (otherwise $3.60/mo for an unused address)
aws ec2 release-address --region $env:AWS_REGION --allocation-id $EIP_ALLOC

# 3. Delete the security group
aws ec2 delete-security-group --region $env:AWS_REGION --group-id $SG_ID

# 4. Delete the IAM profile + role
aws iam remove-role-from-instance-profile --instance-profile-name $env:IAM_PROFILE_NAME --role-name $env:IAM_ROLE_NAME
aws iam delete-instance-profile --instance-profile-name $env:IAM_PROFILE_NAME
aws iam detach-role-policy --role-name $env:IAM_ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam delete-role --role-name $env:IAM_ROLE_NAME

# 5. Unregister the Telegram webhook so the bot doesn't keep retrying a dead URL
$env:TELEGRAM_BOT_TOKEN = "<your bot token>"
.venv\Scripts\python -c "import asyncio,os; from telegram import Bot; asyncio.run(Bot(os.environ['TELEGRAM_BOT_TOKEN']).delete_webhook())"

# 6. (CI/CD only) Tear down the GitHub Actions deploy role
aws iam delete-role-policy --role-name copilot-github-deploy --policy-name copilot-github-deploy-inline
aws iam delete-role --role-name copilot-github-deploy
# Only delete the OIDC provider if no other repo uses it:
# aws iam delete-open-id-connect-provider --open-id-connect-provider-arn arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

---

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `RunInstances` returns `InvalidParameterValue` for the IAM profile | IAM eventual consistency | Wait 30s and retry |
| Caddy logs `no such host` for nip.io | Egress DNS blocked | Check the security group's egress; default-allow-all should fix |
| Caddy logs `HTTP 429 ... too many certificates ... already issued for "nip.io"` | Public LE rate limit on the shared free-DNS domain | Swap to a different free domain: `sed -i 's/nip\.io/sslip.io/g' /etc/caddy/Caddyfile /home/copilot/email-assistant/.env && systemctl reload caddy && systemctl restart copilot`. Both nip.io and sslip.io occasionally fill their LE buckets; alternating works |
| `getWebhookInfo` shows `last_error_message: SSL handshake failed` | Caddy hasn't issued the cert yet | Wait 60s; check `journalctl -u caddy` for ACME errors |
| `journalctl -u copilot` shows `telegram.error.TimedOut` | Cold-start TLS slowness | Already handled by `bot.py`'s 30s `HTTPXRequest` timeout (#25) |
| Bot misses ticks under network flakiness | Was the synchronous-blocking issue | Already fixed in #27 — push tick uses `asyncio.to_thread` |
| `journalctl -u copilot` shows `invalid_grant` for Gmail | Google revoked the refresh token (Testing app, ~7 days idle) | Re-run OAuth on laptop, re-bootstrap `token.pickle` per Step 10. Long-term fix: publish the OAuth app or move it to External + Production status |
| Deploy workflow fails with `Could not assume role` | OIDC trust policy doesn't match the workflow's `:sub` claim | Check the role's trust policy: it must list the exact repo + branch (`repo:OWNER/REPO:ref:refs/heads/main`). A fork or a non-`main` branch can't assume |
| Deploy workflow fails on `Smoke-check /health` after `SSM command succeeded` | uvicorn started but the app errored at runtime; previous version is gone | `aws ssm start-session --target $INSTANCE_ID` then `journalctl -u copilot -n 200`. To restore the previous good commit, re-run that workflow in the Actions UI |

---

## Cost summary

Steady-state monthly:

| Resource | Cost |
|---|---|
| `t4g.nano` 24/7 | ~$3.50 |
| 8 GiB EBS gp3 | ~$0.66 |
| Elastic IP (attached) | $0 |
| Data transfer (low traffic) | ~$0–1 |
| CloudWatch logs free tier (W6-C) | $0 |
| **Total** | **~$5/mo** |

Plus Anthropic API cost (~$0.004 per email analyzed). Run for a year before exceeding $80, vs maintaining a constantly-tunneled laptop.