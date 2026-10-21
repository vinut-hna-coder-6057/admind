# Hosting verification checklist

**Status: preparation checklist only. No host has been provisioned, and no item is marked complete for a live deployment.** Record evidence, date, and operator for every checked item.

## Ownership and access boundary

- [ ] Owner selects provider, region, jurisdiction, DNS name, support contact, and incident contact.
- [ ] Replace example VPN CIDR and hostnames in `deploy/nginx/admind.conf.example` with approved values.
- [ ] Validate the final Nginx configuration with `sudo nginx -t` before reload.
- [ ] Confirm dashboard/admin requests from the VPN succeed and from a non-VPN network are denied (expected 403/connection denial).
- [ ] Confirm unknown `Host` values reach a reject/default server and do not reveal the dashboard.
- [ ] Confirm the public API host exposes only the documented recommendation/health endpoints and returns 404 for unrelated paths.
- [ ] Confirm firewall/security-group rules expose only required TLS ingress and the approved VPN route; deny direct Internet access to ports 8000 and 8501.
- [ ] From an external network, verify the origin IP cannot reach 8000/8501 directly. Record source network and command/output.
- [ ] Confirm proxy overwrites forwarded headers and Uvicorn trusts only loopback proxy headers.
- [ ] Review public unauthenticated API abuse controls, rate limits, body limits, alerting, and escalation path.

## Persistent storage and secrets

- [ ] Mount a durable local filesystem for `/var/lib/admind`; do not put SQLite on NFS/shared network storage.
- [ ] Set correct service ownership and restrictive permissions; verify disk capacity, free-space alerts, and persistence after service/host restart.
- [ ] Provision and seed the catalogue explicitly, then review all ad descriptions and destinations.
- [ ] Store environment secrets outside the repository in an approved secret manager or root-owned file; verify rotation and restore procedures.
- [ ] Persist or intentionally re-download the model cache; test cold-start with outbound model-host access disabled.
- [ ] Confirm app processes run as an unprivileged dedicated account with only necessary writable paths.

## TLS and network

- [ ] Install valid certificates and automate renewal; test expiry alerts and renewal reload.
- [ ] Redirect HTTP to HTTPS and verify certificate chain, hostname, TLS policy, and websocket behavior for Streamlit.
- [ ] Limit egress to required services (DNS, package/update process, approved model host, and YouTube API only when configured).
- [ ] Verify request size limits and rate limits at proxy and application layers.
- [ ] Test readiness and liveness from local and permitted monitoring networks.

## Capacity and resources

- [ ] Select CPU/RAM/disk limits from host-specific measurements of both Streamlit and API together, including simultaneous cold model load.
- [ ] Set service memory/CPU limits and restart behavior; confirm out-of-memory behavior is observable and recoverable.
- [ ] Measure warm latency at expected concurrency and cold startup on the selected host. Do not infer traffic capacity from the repository's small local samples.
- [ ] Confirm one API worker and one host while the limiter is process-local and SQLite has one writer.

## Monitoring and privacy operations

- [ ] Configure service/process health, request latency/error rate, CPU/RSS, disk usage, SQLite errors, TLS expiry, and backup freshness alerts.
- [ ] Set log format and owner-approved journald retention; verify logs contain no title/body, password, session identifier, or client IP.
- [ ] Approve `docs/owner-decisions.md`; publish the applicable privacy notice and support/deletion contact before collecting public user data.
- [ ] Verify each data category's actual deletion path, including backup expiration and retained aggregates.
- [ ] Review and test incident response, credential rotation, and breach escalation.

## Backup, restoration, and rollback

- [ ] Implement a scheduled encrypted off-host backup with separate access credentials, retention, integrity monitoring, and failure alerts.
- [ ] Back up and separately protect deployment configuration/secrets, catalogue source/version, code revision, and any required model artifact.
- [ ] Run `python -m backend.services.sqlite_backup verify --database <backup>` and restore to a new path; compare table counts, indexes, and application-level behavior.
- [ ] Time a full recovery and compare it with the owner-approved RPO/RTO. Repeat periodically and after schema changes.
- [ ] Document and rehearse code rollback, database migration compatibility, DNS/proxy rollback, and no-overwrite restore procedure.
- [ ] Confirm restore never overwrites the only production database or the only good backup.

## Release gate

- [ ] Linux hash-locked clean install, `pip check`, offline tests, compile, Bandit, Ruff, and pip-audit pass in hosted CI.
- [ ] Reviewer labels are human-generated; all candidate pairs for chosen videos are complete; held-out labels have not informed tuning.
- [ ] Security, privacy, hosting, recovery, and capacity evidence is reviewed and signed off by the owner.
- [ ] Final deployment plan and rollback operator are approved before any deployment action.
