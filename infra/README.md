# Infrastructure

Templates used during the Week 6 EC2 deployment. Real values are filled in by `docs/AWS_DEPLOY.md`; nothing in this directory is consumed at runtime by the app itself.

| File | Lands at on the instance | Purpose |
|---|---|---|
| `Caddyfile.template` | `/etc/caddy/Caddyfile` | Reverse proxy + auto-TLS via Let's Encrypt for `<eip>.nip.io` |
| `copilot.service` | `/etc/systemd/system/copilot.service` | systemd unit running `uvicorn` under the `copilot` user |

Substitution placeholders use `<UPPERCASE>` (e.g. `<EIP_DASHED>`) so a `sed` pass during deploy is unambiguous.

See [`docs/AWS_DEPLOY.md`](../docs/AWS_DEPLOY.md) for the full provisioning runbook.