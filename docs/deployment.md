# Production deployment preparation

Status: proposed single-host deployment design; no public host has been selected or provisioned.

## Shape

Run Streamlit on `127.0.0.1:8501` and the optional FastAPI service on `127.0.0.1:8000`, behind Nginx with TLS. The dashboard calls the recommender in-process; FastAPI is a separate public integration surface. Keep one application host and a local persistent SQLite file at `/var/lib/admind/admind.db`. Do not place SQLite on a network filesystem or share it between replicas. Move to a server database before adding app replicas or substantial concurrent writes.

The dashboard is reachable only from the VPN CIDR in the example Nginx site; replace the example subnet with the real VPN subnet. The dashboard's admin view also checks its server-side Streamlit session and is password protected and read-only. The separate API proxy exposes `GET /api/`, `GET /api/livez`, `GET /api/readyz` (and `/api/health`), and unauthenticated `POST /api/recommend-ad`. There are no admin API routes. The API surface intentionally permits public recommendations; it receives only a video title and options.

Nginx should enforce TLS, a small request body limit, and per-IP request limiting on `/api/`. The application also limits recommendation calls per process, but that limiter is not shared across workers. Keep API workers at one until rate limiting is moved to shared infrastructure. `/livez` checks process liveness; `/readyz` and the compatibility `/health` endpoint check that the database and usable ad catalogue are available.

## Provisioning outline

1. Use a supported Linux host, a dedicated unprivileged `admind` account, and persistent local storage. Install dependencies into a virtual environment from the repository requirements.
2. Provision the database explicitly with `python -m backend.services.initialize_database --database /var/lib/admind/admind.db --seed-catalog`. Review the imported starter catalogue before exposing the service. Runtime startup in production does not create or seed the catalogue.
3. Copy `.env.production.example` to `/etc/admind/admind.env`, replace placeholders, set restrictive ownership and mode, and generate an `ADMIN_PASSWORD_HASH` with the project's password-hash helper. The cookie secret must be random and at least 32 characters. Never commit environment files.
4. Set `HF_HOME=/var/cache/admind/huggingface`; prewarm the configured embedding model on the host during release preparation, or allow first startup to download it. The latter increases startup latency and requires outbound access to the model host.
5. Install the example systemd units and Nginx site, configure actual certificate paths and domain, then start the services. Verify `/livez`, `/readyz`, dashboard access, admin rejection/acceptance, and a representative recommendation before changing DNS or public firewall rules.
6. Keep the database and model cache on persistent local volumes. Back up SQLite with the backup CLI and copy verified backups to an access-controlled, encrypted location with independent credentials.

The examples use `/opt/admind` as the code path. Change it consistently if the release is installed elsewhere. The environment file should be owned by root and readable by the `admind` group only (mode `0640`); data/cache directories should be owned by the service account with mode `0700`. Nginx certificate issuance, firewall rules, DNS, secret storage, and encrypted off-host backup are host-owner tasks.

## Public surface and controls

The API recommendation endpoint does not require an application API key. Treat it as public: use Nginx rate limiting, request-size limits, TLS, and monitoring. The in-process IP limiter is a secondary guard and can be bypassed by multiple workers or hosts. Do not pass client-supplied forwarded IP headers through the proxy; the example overwrites them from the connection peer, and Uvicorn trusts forwarded headers only from loopback. The Nginx example isolates the dashboard on a VPN-only hostname and the API on its own public hostname. Host/cloud firewall rules must expose only Nginx ports 80/443, permit the chosen VPN route, and deny direct public access to the origin's application ports. Verify the public origin cannot reach port 8501 or 8000 directly.

Admin access uses a configured PBKDF2 password hash and fails closed when absent. Streamlit's signed cookie secret must be stable across restarts. The admin page is read-only, but the current app has no account system, global login throttling, or identity-provider integration. Until those are provided, restrict admin access at the deployment edge (for example, VPN or an identity-aware proxy); the app password alone is not a sufficient hostile-internet control. Public deployment also needs a documented privacy notice, retention choice, incident contact, and owner approval of the hosting region and backup destination.

## Scaling and capacity

The embedding model and category index are held in process memory. Running both services duplicates that memory. The model cache is regenerable from its upstream model source but is not included in the SQLite backup; prewarm it before launch and retain an approved offline recovery copy only if required. Keep one worker per service on a small host, measure memory and latency under the intended catalogue and request mix, and size the host with headroom. This repository has no evidence for a safe public traffic ceiling; use the local benchmark and a host-specific load test before setting one.

## Rollback

Take and verify a SQLite backup before deploying a release or running migrations. Keep the previous code release available. Roll code back first if health checks fail; restore a database backup only when a migration or data corruption requires it, and only to a new path for verification before switching the configured path. Never overwrite the only live database copy.

## Hosting options and cost assumptions

The preferred *type* of host is one Linux VM with local persistent storage, Nginx, and systemd. The API process measured about 570 MB RSS during a brief warm burst; Streamlit loads a separate model/index, so combined use is higher. A 4 GiB RAM / 2 vCPU machine is a planning floor only, not a measured minimum or traffic guarantee. Measure both services and cold-start peaks on the selected host.

| Option | Fit | Cost / verification |
|---|---|---|
| General Linux VM | Best match for the checked-in units, VPN routing, Nginx, and one local SQLite writer. | Compute is region/size specific and no host or region is selected. DigitalOcean documents attached volume storage at $0.10/GiB-month; compute is separate. AWS EC2 and EBS are separate, region-priced resources. Total remains unverified. |
| Railway-style PaaS | Supports service deployments and persistent volumes/backups, but requires replacing systemd/Nginx setup, validating private/VPN ingress, Python 3.14 wheels, and one-replica SQLite semantics. | Current docs list Hobby $5/month, with usage pricing of $10/GB-month RAM, $20/vCPU-month, $0.15/GB-month volume, and $0.05/GB egress. 4 GiB + 2 vCPU is roughly $80/month compute usage before storage/egress; pricing and plan limits must be checked at selection. Free plan memory is 0.5 GiB per service, below the measured API process peak. |
| AWS EC2 + EBS | Flexible Linux VM, durable attached storage, snapshots, and network controls, with more operational setup. | Use the current regional calculator. Include compute, EBS, snapshots, transfer, monitoring, TLS, domain, and backups. No quote is estimated. |

Provider documentation checked 2026-10-20: [DigitalOcean volume pricing](https://docs.digitalocean.com/products/volumes/details/pricing/), [DigitalOcean Droplet pricing](https://docs.digitalocean.com/products/droplets/details/pricing/), [AWS EC2 pricing](https://aws.amazon.com/ec2/pricing/), [AWS EBS pricing](https://aws.amazon.com/ebs/pricing/), [Railway plans/limits](https://docs.railway.com/pricing/plans), and [Railway resource pricing](https://docs.railway.com/pricing). Prices vary by region, usage, tax, and plan changes; they are not a quote.

SQLite is appropriate only for one host and modest write volume. Move to a managed relational database before multiple replicas, multiple independent writers, or a shared filesystem are needed. Draft targets for owner review: warm recommendation p95 under 500 ms at four concurrent requests; cold recommendation within 60 seconds after startup; four concurrent cold calls complete without duplicate model loads; RPO at most 24 hours and RTO at most four hours with daily encrypted off-host backup. These are proposed targets, not verified SLOs or approved recovery objectives.
