# Operations runbook

This runbook describes the proposed single Linux host. Paths match the example systemd units.

## Start, stop, and health

```sh
sudo systemctl start admind-streamlit admind-api
sudo systemctl status admind-streamlit admind-api
curl -fsS http://127.0.0.1:8000/livez
curl -fsS http://127.0.0.1:8000/readyz
sudo systemctl stop admind-api admind-streamlit
sudo systemctl restart admind-streamlit admind-api
```

Use `/livez` for process liveness and `/readyz` for database/catalogue readiness. Public proxy checks should use HTTPS and the configured domain. A failed readiness check means the app is not ready to serve recommendations.

## Logs

```sh
sudo journalctl -u admind-api -u admind-streamlit --since '1 hour ago'
sudo journalctl -u admind-api -f
```

API request logs include request ID, path, status, and elapsed time. Do not enable request-body logging. On systemd hosts, set and review `/etc/systemd/journald.conf` `SystemMaxUse` and `MaxRetentionSec` using the owner-approved log period, then restart `systemd-journald`. The app does not rotate files itself. Validate log retention against disk headroom and incident-investigation needs.

## Database backup and restore

```sh
sudo -u admind /opt/admind/.venv/bin/python -m backend.services.sqlite_backup backup --source /var/lib/admind/admind.db --output /var/backups/admind/admind-YYYYMMDD.db
sudo -u admind /opt/admind/.venv/bin/python -m backend.services.sqlite_backup verify --database /var/backups/admind/admind-YYYYMMDD.db
sudo -u admind /opt/admind/.venv/bin/python -m backend.services.sqlite_backup restore --backup /var/backups/admind/admind-YYYYMMDD.db --output /var/lib/admind/restore-check.db
```

Backup and restore refuse to overwrite existing output. Test restored files and counts before any cutover. This command covers SQLite only; preserve catalogue source/version, application release, environment configuration (in a secret manager), and any required model cache separately. Transfer backups to encrypted, restricted storage; local copies do not protect against host loss. Draft owner-review targets are RPO ≤24 hours and RTO ≤4 hours; they require daily encrypted off-host backups and a restore completed within four hours. Neither the backup schedule nor the targets are approved or operational yet.

## Retention

```sh
sudo -u admind /opt/admind/.venv/bin/python -m backend.services.retention --database /var/lib/admind/admind.db --history-days 30 --feedback-days 90 --events-days 90
sudo -u admind /opt/admind/.venv/bin/python -m backend.services.retention --database /var/lib/admind/admind.db --history-days 30 --feedback-days 90 --events-days 90 --apply
```

The first command reports counts only. These example ages are proposed only; select periods through the published privacy policy. Do not schedule deletion until the owner approves them and backup handling. Run a verified backup before deletion.

## Release and rollback

1. Review changes and dependency scan output; run tests, compile checks, and offline evaluation.
2. Back up and verify the database. Record the deployed code revision.
3. Install the release while retaining the prior release; restart services and verify readiness and a sample request.
4. If checks fail, restore the previous code and inspect logs. Do not restore database data unless needed; first restore to a separate path and verify.

## Common issues

- `readyz` returns 503: check `DB_NAME`, file permissions, SQLite integrity, and that at least one ad has both a name and description.
- Production startup refuses configuration: set an absolute persistent `DB_NAME` outside the source tree, a stable 32+ character cookie secret, and a valid admin password hash.
- First recommendations are slow: the embedding model may be initializing/downloading. Confirm outbound model-host access or prewarm the persistent `HF_HOME` cache.
- Recommendation request gets 413: the 16 KiB API body limit was exceeded; send only the required title and options.
- Recommendation request gets 429: the per-process limiter is active. Review proxy rate limiting and client retry behavior; do not add API workers as a workaround.
