# AdMind production-readiness audit

**Audit date:** 2026-10-20  
**Target assessed:** local single-instance Streamlit dashboard and FastAPI service, using one SQLite database  
**Overall status:** **NOT READY for production deployment**

This audit preserves a pre-existing dirty working tree. The branch was `admind-production-upgrade` and contained substantial uncommitted recommendation, analytics, UI, documentation, and test work before this audit. Only the audit-specific edits listed near the end are attributed to this pass. No database rows, reviewed labels, or source datasets were intentionally changed. Smoke tests and benchmarks used disposable SQLite files; the evaluator read the packet and wrote its report under `artifacts/`.

## Executive summary

The app has a coherent local architecture and the recommendation ranker keeps semantic relevance separate from mode, audience, CTR, and global feedback. The SQLite migration and event accounting have focused regression coverage. The current local test suite passes, the API rejects malformed inputs, and missing metadata or model failures have safe title-only/lexical fallbacks. A manual title override now makes the dashboard usable when the optional YouTube API key is unavailable. API readiness now fails closed when SQLite or a usable ad catalogue is unavailable.

Recommendation quality is **NOT YET VERIFIED**. The packet contains 12 source videos and 120 catalogue pairs, all `pending`; there are no human labels, so no NDCG@5, Precision@5, Recall@5, MRR, rank-failure examples, or current-versus-baseline result exists. Do not tune on the held-out split and do not claim improved quality. Production deployment is also blocked by absent deployment/backup/monitoring controls, undocumented privacy retention, an unauthenticated API that needs network isolation, and unpinned dependencies without a completed vulnerability scan.

## Verified architecture and execution paths

- Streamlit starts at `frontend/app.py`, initializes the database and seeds `backend/datasets/ads_dataset.csv`, then renders Dashboard, Analytics, or the view-only Admin page. The dashboard calls the shared recommender directly; it does not call FastAPI.
- FastAPI starts at `backend/api.py`; lifespan initializes the same SQLite schema and seeds the catalogue. `POST /recommend-ad` validates the title (1–500 characters), mode, and audience, then calls the shared synchronous ranker. The handler now runs as a synchronous FastAPI route so inference is dispatched through FastAPI's worker threadpool.
- `backend/services/recommender_engine.py` loads SQLite ads, rejects opaque IDs and non-descriptive titles, skips missing offering copy and duplicate offerings, and ranks using cosine similarity between the title and ad name-plus-description. Lexical overlap breaks semantic ties and provides a fallback. Detected category is context/explanation only. The score is raw and is not a probability.
- `backend/services/embedding_service.py` lazily loads `all-MiniLM-L6-v2`; `backend/services/vector_store.py` builds nearest-neighbour category context from the video-title TSV and uses FAISS when available or NumPy otherwise. Model failure falls back to lexical ad ranking. This audit added cached model/index failure handling to avoid rebuilding/retrying failed initialization for every request; process restart is required to retry model loading.
- `backend/services/youtube_api.py` validates supported YouTube URLs and calls official `videos.list(part="snippet")` with a five-second HTTP timeout when `YOUTUBE_API_KEY` is configured. The current integration returns title and tags, not description. The dashboard can use a manual title when metadata cannot be fetched. Description use is deferred until labels can support a title-only versus title-plus-description comparison. No transcript scraping was added. YouTube's API snippet exposes description in the same response ([Videos: list API reference](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)); automated access is subject to the [YouTube Terms](https://www.youtube.com/t/terms) and [Developer Policies](https://developers.google.com/youtube/terms/developer-policies-guide).

## Recommendation quality and evaluation

Verified repository data: `youtube_analytics.csv` has 537 records in 12 known categories; `ads_dataset.csv` and the current SQLite `ads` table each have 30 ads. `videos_dataset.csv` is separate and is not the live ranking source. The label generator selects at most one source video per category using a fixed seed and stable IDs derived from dataset row/content; candidate selection includes lexical-overlap ads, adjacent-category ads, and seeded samples across the catalogue. It does not select only the current ranker's top results. The packet has 12 videos, 9 development and 3 held-out, with 10 ad pairs per video.

The human workflow and 0–3 usefulness guidance are in `docs/recommendation-evaluation.md`; `docs/recommendation-labels-template.csv` and `docs/recommendation-labels.csv` have provenance, stable IDs, source channel/date/category, ad name/description/category, split, status, label, and notes. Reviewers should not see model rankings, should label insufficient context as `insufficient_information`, and should leave genuinely unreviewed pairs `pending`. The evaluator excludes incomplete video candidate sets from metrics. It does not infer labels.

Current evaluation output:

| Quantity | Result |
|---|---:|
| Videos / candidate pairs | 12 / 120 |
| Development / held-out videos | 9 / 3 |
| Rated / pending / insufficient pairs | 0 / 120 / 0 |
| Relevance labels 0 / 1 / 2 / 3 | 0 / 0 / 0 / 0 |
| Complete labeled videos | 0 |
| NDCG@5, Precision@5, Recall@5, MRR | Not available (`metrics: null`) |
| Top-rank human failure cases | Not available |

The evaluator defines a reproducible previous **content-scoring baseline** (`max(title-description cosine, inferred-category/ad-category cosine)`) and a replay of the current title-to-offering cosine, lexical tie-break, and duplicate suppression. Historical production order cannot be reconstructed: per-request CTR, mode, audience, feedback, and session feature snapshots were not recorded. Since no videos are fully labeled, neither the reproducible baseline nor current ranker can be compared on valid human judgments. Recall, when available, is relative to packet candidates rather than the entire catalogue. The 3-video held-out split will be diagnostic and underpowered.

No quality-driven score change was made. After labeling, inspect top ads by relevance, candidate-vs-baseline regressions, and labels by source category. Classify failures as context, ad copy, candidate sampling/retrieval, semantic score, or duplicate filtering. Change weights or context only on development labels; report held-out once, unchanged.

## Confirmed findings and priority

Severity means: **P0** critical security/data loss/service integrity; **P1** production blocker/severe correctness; **P2** important quality/operational work; **P3** optional enhancement.

| Priority and finding | Evidence and impact | Status / remaining work |
|---|---|---|
| **P1 — Recommendation quality unverified** | All 120 packet pairs are pending; evaluator returns `awaiting_labels` and null metrics. No human failure cases can be diagnosed. | **Open / evidence blocked.** Humans must label complete candidate sets, ideally with a second reviewer sample. No claim of relevance improvement is supported. |
| **P1 — No production operations or deployment target** | No Docker/process configuration, CI workflow, backup/restore script, monitoring, log rotation, rollback procedure, or deployment target was found. README runs local services bound to `127.0.0.1`. | **Open.** Select target and supply persistent storage, TLS/reverse proxy, service supervision, backups, restore drill, monitoring, and rollback plan before deployment. |
| **P1 — Privacy lifecycle is undefined** | History stores video title and session UUID; feedback and analytics persist in SQLite. No retention, user deletion, or privacy notice was found. | **Open.** Define data purpose, retention/deletion, access, backup encryption, and user notice for the deployment jurisdiction. |
| **P1 — First video request has cold model/index delay** | A local benchmark on the real 30-ad catalogue measured 13.5–17.3 seconds for the first rank call while the 537-title index/model initialized. Ten warmed repeats for one title had 53.6–58.2 ms median and 63.4–103.2 ms maximum across runs. | **Measured, not load-tested.** Define acceptable first-request latency and consider prewarming during controlled startup or moving initialization to background readiness. No user-facing latency objective exists. |
| **P2 — API has no authentication** | `/recommend-ad` accepts unauthenticated requests; the current documented command binds loopback and README requires deployment network controls. Limiter is in-process and keyed by remote address. | **Open / deployment-dependent.** Keep behind trusted network controls or add an auth design before remote exposure; use shared rate-limit storage for multiple workers. |
| **P2 — Dependencies are unpinned and advisory scan unavailable** | Requirements list packages without version pins/lock; `pip check` passes in the installed Python 3.14.3 environment, but `pip-audit`, Bandit, and Ruff are not installed. No vulnerability scan result is available. | **Open.** Establish supported Python/dependency constraints, generate a lock/build artifact, and run an approved advisory scanner in CI. |
| **P2 — Catalogue seeding silently tolerates failure** | `insert_ads()` catches errors and logs them; Streamlit startup continues. API readiness now catches empty/unusable catalogue, but the dashboard itself has no explicit catalogue readiness banner. | **Partially addressed.** API readiness is fixed and tested; surface an actionable dashboard startup state and decide whether catalogue seed errors should fail startup. |
| **P2 — YouTube description is available but unused** | Official snippet request returns title/tags only even though description is in the same `snippet`; title-only ranking may lack context. | **Deferred pending evidence.** Add bounded in-memory description context and compare against title-only using the same human labels, after terms/privacy review. |
| **P2 — Genuine click metric is not instrumented in the UI** | Catalogue has no destination URL and no click control; CTR chart can only report recorded destination clicks, currently none from dashboard workflow. | **Open / capability gap.** Add destination and click instrumentation only with a defined ad-serving/user flow; do not treat positive feedback as click. |
| **P2 — SQLite backups, retention, and multi-instance behavior are unspecified** | One local SQLite DB stores catalogue/history/analytics/feedback. No backup/restore or cleanup process exists; file locking is 30 seconds and rate limiting is per-process. | **Open.** Verify backup/restore and persistence; choose one instance or migrate storage/limiting for horizontally scaled deployment. |
| **P2 — Stale ranking explanation in README** | Ranking section still described category/mode/audience/CTR/feedback ranking and a diversity penalty, contradicted by live ranker. | **Fixed and verified by source review.** README now documents title-to-offering scoring and separates business signals. |
| **P2 — API health falsely returned healthy** | Previous `/health` always returned `{"status":"healthy"}`, even with missing DB/catalogue. | **Fixed and tested.** It now verifies SQLite query and at least one non-empty name/description ad; returns HTTP 503 with safe detail otherwise. |
| **P2 — Synchronous ranking ran inside an async route** | `async def recommend` executed synchronous model/SQLite inference directly on the event loop. | **Fixed and regression-tested.** Route is sync and FastAPI runs it in the worker pool. |
| **P2 — Dashboard depended on optional API key for a title** | Without a key or successful request, the dashboard passed an empty title and could not use the engine, despite title-only ranking support. | **Fixed.** Optional manually entered/corrected title works without API access; it takes precedence over fetched metadata. Unit and AppTest workflow checks pass. |
| **P2 — Feedback default could silently mean positive** | The radio defaulted to `Relevant`; submit without an explicit choice persisted positive feedback. | **Fixed.** A `Select one` default is required before saving; helper regression test verifies mapping. |
| **P2 — Model/index load failure was retried on each request** | Model initialization errors were not cached; the vector store remained uninitialized, causing repeated dataset/index/model work after failure. | **Fixed and failure-injection tested.** Model failure is cached for process lifetime; category index failure caches an empty general-context fallback. Restart to retry. |
| **P2 — Broad category was presented as an “AI TAG”** | Category is nearest-neighbour context, not an AI-derived semantic tag and does not alter rank. | **Fixed.** UI now labels it “Video category context.” |
| **P3 — Recommendation scores are not calibrated** | Cosine/lexical score is raw and not a probability or user usefulness estimate. | **Open by design.** Preserve honest terminology; calibration requires judged data and a separate objective. |

## Backend, database, analytics, frontend, and security

### Backend/API

Input constraints and rate limiting exist. Error responses hide internal details; server logs retain stack traces for debugging. `/health` now checks essential data availability. The recommendation route is synchronous and no longer blocks the async event loop, but local model initialization may still occupy one worker for many seconds. A `None` rank result is currently returned as HTTP 200 JSON `null`; this is compatible with existing behavior but is a response-contract weakness to resolve only with client/version review. Rate limits are per process and do not protect multiple workers as a shared quota.

### Database and analytics

The SQLite schema uses additive `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE` checks, with indexes for event and session queries. Tests exercise old history migration, idempotent impressions/clicks, click-impression association, and separation of feedback from clicks. Existing legacy aggregate counts are preserved but excluded from valid event-derived dashboard numbers. Impressions are recommendation displays; clicks are not produced by the current dashboard because no destination link exists; feedback is a separate ad-level signal. No conversions, time-series charts, user-scoped feedback, retention, or restore process is implemented. Test migrations used disposable DBs; the existing `admind.db` was not migrated by the audit.

### Frontend

Dashboard, Analytics, and authenticated view-only Admin paths rendered under Streamlit AppTest without exceptions. A local Streamlit process served `127.0.0.1:8765` with HTTP 200 using a temporary DB. Manual title override covers missing metadata. Score labels remain raw. No live YouTube call was made. External Google Fonts are referenced by the shell; offline visual behavior was not evaluated. `unsafe_allow_html=True` is used for static application-controlled markup; current user title/ad text is displayed through Streamlit text components, not interpolated in those HTML templates.

### Security and privacy

Admin password verification uses PBKDF2-HMAC-SHA256, a bounded iteration count, and constant-time comparison; missing/malformed hash fails closed. There are no admin API routes. SQL data values are parameterized in inspected paths. No CORS middleware was found. The API is unauthenticated, so loopback/network isolation is required. `.env` was absent and `.env.example` exists; a heuristic scan found no high-confidence AWS/Google/GitHub key or private-key patterns, but no dedicated secret scanner ran. No dedicated vulnerability scanner ran (`pip-audit` and Bandit absent). This is a practical code review, not a guarantee of security. Treat stored video titles as potentially sensitive browsing data.

## Performance and reliability check

Benchmark was executed offline (`HF_HUB_OFFLINE=1`) with the local cached `all-MiniLM-L6-v2`, Python 3.14.3, the real 30-row SQLite catalogue copied read-only into a temporary DB, one fixed title, one cold request followed by 10 warmed requests. The reproducible run took 18.02 s cold, 49.09 ms warm median, and 98.33 ms warm maximum. The cold number includes index construction over the 537 video titles. This is a local microbenchmark, not production traffic or load testing; CPU/hardware details and a latency target were not captured. The benchmark script changes no rows in the source DB.

## What works and was verified

- 23 focused unit tests pass after audit changes; compile check passes.
- `pip check` reports no broken installed requirements.
- API health returns 503 with an empty catalogue and 200 with a usable ad; invalid requests return 422 and mocked rank failure returns generic 500.
- Streamlit HTTP startup and Dashboard/Analytics/Admin AppTest paths completed with no page exceptions (Admin path tested in authenticated session state).
- Title override preference, explicit feedback choice, model-load failure cache, general-category fallback, migration preservation, analytics idempotence, opaque video ID rejection, duplicate/empty ad handling, ranking behavior, and empty vector store have regression coverage.
- The offline evaluator ran and correctly reported no metrics rather than fabricating them.

## Remaining blockers and recommended order

1. Human-label complete candidate sets using the written guidance, with a second reviewer on a sample; keep held-out labels sealed from tuning.
2. Use those labels to compare current ranker against the reproducible content baseline, inspect top-ad errors and per-video regressions, and only then test bounded video description context or rank changes.
3. Choose a deployment target and implement deployment-specific auth/network isolation, TLS, persistence, backup/restore drill, monitoring, retention, and rollback.
4. Pin and scan dependencies in CI and define supported Python and latency targets; measure under expected concurrency.
5. Decide whether valid click tracking is a product requirement and provide ad destinations before reporting CTR as a performance outcome.

No action in this audit requires user approval. Manual labeling, deployment infrastructure/target decisions, and privacy retention policy require human input before the corresponding work can be completed.

## Commands and actual results

Commands were run from repository root with the installed Python 3.14.3 executable (`C:\Users\vinut\AppData\Local\Python\pythoncore-3.14-64\python.exe`). Generic `python` commands work with an activated project environment as in README.

| Command/check | Result |
|---|---|
| `python -m compileall -q backend frontend tests` | Pass |
| `python -m unittest discover -s tests -v` | Pass; 23 tests (20 before audit-specific regression additions, 23 final) |
| `python -m pip check` | Pass: no broken requirements |
| `git diff --check` | Pass; only pre-existing LF-to-CRLF notices |
| `python -m pip show pip-audit bandit ruff` | Not available: none installed |
| `python -m backend.services.offline_evaluation --labels docs/recommendation-labels.csv --output artifacts/recommendation-evaluation.json --k 5` | `awaiting_labels`; 12 videos, 120 pairs, 0 rated, metrics null |
| `$env:HF_HUB_OFFLINE='1'; python -m backend.services.benchmark_recommender --db admind.db --title 'How to use Python for data analysis' --iterations 10` | Cold 18.02 s; warm median 49.09 ms; warm max 98.33 ms; 30 SQLite ads; 537-title context index |
| Streamlit run on `127.0.0.1:8765` with temporary `DB_NAME`, then HTTP GET `/` | HTTP 200; process stopped after smoke test |
| Streamlit AppTest, default Dashboard, Analytics selection, authenticated Admin selection | 0 page exceptions in each path |
| Streamlit AppTest manual-title submission with no API key, then default feedback submit | Recommendation used manual title; no API request; placeholder feedback produced warning and saved nothing |
| Heuristic source/docs/template key/token/private-key scan | No high-confidence matches; not a comprehensive secret scanner |

## Audit-specific edits

This pass edited:

- `backend/api.py` — truthful readiness; synchronous recommendation handler and useful safe server logging.
- `backend/services/embedding_service.py`, `backend/services/vector_store.py` — negative-cache model/index initialization failures and preserve lexical/general fallback.
- `backend/services/benchmark_recommender.py` — repeatable cold/warm benchmark against a read-only source catalogue and disposable DB copy.
- `backend/services/youtube_api.py`, `frontend/ui/dashboard_page.py` — title selection helper and manual title fallback; require explicit feedback selection.
- `frontend/ui/components.py` — accurate category-context label.
- `README.md` — remove superseded ranking formula and document manual title input.
- `tests/test_core_behaviors.py` — health readiness, title fallback, feedback choice, and model/index failure regressions.
- `docs/production-readiness-audit.md` — this evidence and remaining-work record.

Pre-existing uncommitted edits in other files were left intact. The offline evaluator output was generated at `artifacts/recommendation-evaluation.json`; no scored-pairs file was produced because there were no fully labeled videos. The report contains no labels or ranking metrics.

## Production deployment preparation follow-up (2026-10-20)

The follow-up work added a proposed one-host deployment package and additional local verification. The status remains **NOT READY for public deployment**: no host/domain or jurisdiction is selected, no privacy retention policy is approved, API recommendations remain unauthenticated, scanner results remain unavailable, and the human-label packet is still unscored.

- Deployment architecture and systemd/Nginx templates are in `docs/deployment.md`, `deploy/systemd/`, and `deploy/nginx/`. They assume one Linux host, local persistent SQLite, loopback-bound services, TLS at Nginx, one API worker, body/request limits, and no public infrastructure changes.
- Production startup now checks absolute persistent DB path, cookie secret, password hash, and a usable catalogue, and does not seed the catalogue. `backend.services.initialize_database` is the explicit provisioning command.
- `/livez` and `/readyz` are available; `/health` remains a readiness alias. Request middleware rejects bodies above 16 KiB and writes structured request ID/path/status/latency logs without request bodies or client IP. Admin page checks authorization internally as well as through the router.
- `backend.services.sqlite_backup` performs online SQLite backups, integrity checks, and restore to a new non-existing path. Its restore drill passed with disposable test data. `backend.services.retention` defaults to a count-only dry run and deletes history, feedback, and events only with explicit `--apply`; no period is selected by the project.
- Privacy inventory, operator runbook, production environment template, and CI checks were added. CI has not run in this local workspace. Requirements remain unpinned; `pip-audit`, Bandit, Ruff, and a dedicated secret scanner are unavailable locally.
- All 25 unit tests pass after the follow-up. Local `pip check`, compile, and recommendation evaluation should be rerun with the exact commands below before release.
- Repeated current benchmark on the 30-ad catalogue / 537-title dataset (Python 3.14.3, cached `all-MiniLM-L6-v2`) measured 28,214.39 ms cold, 87.33 ms warm median, and 165.10 ms warm max. These values differ from the earlier run and show why machine/runtime state must accompany comparisons; this is not a public capacity claim.
- Disposable local API check on loopback, four concurrent first requests: 4/4 HTTP 200, 18.218 s total, p50 18,105 ms, p95/p99 18,214 ms, measured API-process peak RSS 570.2 MB and CPU 99.8% in the subsequent warm rate-limit run. An 11-call warm rate-limit probe produced 10 HTTP 200 and 1 HTTP 429 in 1.343 s (p50 786.27 ms, p95/p99 1,341.09 ms). These are narrow smoke/load samples, not a capacity test; the cold sample did not measure server process memory.

The first available local port (8000) was already occupied, so the disposable API check used port 8766; no existing process was stopped or modified. Both test database files were outside the repository. No live YouTube request was made.

### Reproduction commands

Run from the repository root. Replace `python` with the local Python 3.14 executable in this Windows workspace if the launcher is unavailable.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q backend frontend tests
python -m pip check
git diff --check
python -m backend.services.offline_evaluation --labels docs/recommendation-labels.csv --output artifacts/recommendation-evaluation.json --k 5
$env:HF_HUB_OFFLINE='1'; python -m backend.services.benchmark_recommender --db admind.db --title 'How to use Python for data analysis' --iterations 10
$db = Join-Path $env:TEMP ("admind-backup-" + [guid]::NewGuid().ToString("N") + ".db")
$backup = "$db.backup"
$restore = "$db.restore"
python -m backend.services.initialize_database --database $db --seed-catalog
python -m backend.services.sqlite_backup backup --source $db --output $backup
python -m backend.services.sqlite_backup verify --database $backup
python -m backend.services.sqlite_backup restore --backup $backup --output $restore
python -m backend.services.sqlite_backup verify --database $restore
python -m backend.services.retention --database $db --older-than-days 365
$env:DB_NAME = Join-Path $env:TEMP ("admind-load-" + [guid]::NewGuid().ToString("N") + ".db")
$env:ADMIND_ENV='development'; $env:HF_HUB_OFFLINE='1'
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8766 --workers 1
# In a second shell, use the API PID printed by Uvicorn:
python -m backend.services.local_load_test --port 8766 --requests 4 --concurrency 4 --mode valid --pid <API_PID>
python -m backend.services.local_load_test --port 8766 --requests 11 --concurrency 11 --mode rate-limit --pid <API_PID>
# Stop only this Uvicorn process with Ctrl+C.
```

The backup commands above write test artifacts and must use fresh output names; the CLI intentionally refuses overwrite. The retention command is dry-run. Start a disposable local API first for load checks and stop only the process started for that check. The exact load values in this report came from ephemeral databases and are not expected to repeat exactly.

## Final security, privacy, and deployment readiness verification (2026-10-20)

This section supersedes earlier follow-up statements in this document that scanner tools were unavailable, dependencies were wholly unpinned, and recovery/load checks still needed to be performed. The production decision remains **NOT READY for public deployment**. No host, DNS, cloud resources, public firewall, or live service was changed.

### Verification completed

- The complete local suite passes: **28 tests** using Python 3.14.3 and `HF_HUB_OFFLINE=1`. Compileall, `pip check`, and `git diff --check` pass. Ruff passes the configured correctness subset (`E4,E7,E9,F`); the broader default Ruff rule set has unrelated style and broad-exception findings and is not claimed clean. Bandit `-ll` scanned 2,755 lines and reported zero issues at all severities/confidences.
- A SQLite recovery drill against the existing `admind.db` completed without changing it: online backup, backup integrity verification, restore to a new temp file, and restored-file verification all passed. The source, backup, and restored database had `ads=30`, `analytics=0`, `analytics_events=0`, `feedback=0`, and `history=0`; indexes were preserved. This proves the local CLI round trip only. It does not prove encrypted off-host backup, automated scheduling, host-loss recovery, or the proposed RPO/RTO.
- After batching the category-title embeddings, a cold local microbenchmark on the 30-ad catalogue and 537-title dataset measured **20.7 s cold**, **136 ms warm median**, and **340 ms warm maximum** over 10 warm calls. A fresh disposable API process handled four simultaneous cold recommendation requests with **4/4 HTTP 200**, **29.87 s total**, p50 29.64 s, p95/p99 29.87 s, peak API RSS **644.3 MB**, and sampled peak CPU **1,212%** (multi-core process percentage). This is a local smoke/load sample, not a capacity or production SLO result. The provisional four-concurrent/60-second cold target was met in this run; warm p95 under 500 ms at four concurrent users was not separately remeasured.
- Current offline evaluation still reports **12 videos, 120 pairs, 0 rated, 120 pending**, no complete labeled videos, and null metrics. Human relevance distribution and rank failure cases are unavailable. No labels were generated or inferred. No quality claim is supported.
- The Nginx example splits the public unauthenticated recommendation API from the VPN-only dashboard/admin hostname and keeps app ports loopback-bound. This is configuration intent, not an externally tested boundary. Actual VPN CIDR, domains, certificates, host/cloud firewall, and direct-origin reachability still require deployment-specific verification. No public deployment has been performed.

### Dependency and privacy findings

`requirements.txt` is now constrained for the tested direct Python 3.14 application set, with a separate `constraints-security.txt` adding advisory-fix minimums. This is **not a complete reproducible lock**: it is not fully transitive-pinned or hash-locked, and dependency resolution/install in Linux CI has not yet been demonstrated. `requirements-dev.txt` adds pip-audit, Bandit, and Ruff. CI has been updated but has not run on a hosted runner.

The declared requirements audit (`pip-audit -r requirements.txt`) reported no known vulnerabilities for the versions it resolved. A separate local audit of the installed application runtime dependency closure identified 13 installed packages with known advisories: anyio, cryptography, fsspec, GitPython, httplib2, Pillow, pyasn1, sentence-transformers, setuptools, starlette, torch, tornado, and transformers. The installed versions do not necessarily match a fresh resolution under the new constraints. The audit output did not provide severity, so this report does not assign one. The broader whole-workstation environment also contained unrelated vulnerable packages and is not attributed to AdMind. Regenerate a full platform-specific lock, install it in clean CI, and rerun the advisory scan before release.

The privacy inventory now covers video titles/session UUIDs, feedback, analytics event and aggregate fields, catalogue copy, API logs, transient admin state, secrets, backup copies, and proposed retention. The suggested 30-day history, 90-day feedback/events, 30-day logs/backups periods are **not owner-approved policy**. Retention remains manual and dry-run by default; deleting a live row does not erase backup copies. The app has no individual account identity for user-specific export/deletion. A published privacy notice, jurisdiction, lawful purpose, deletion request path, log/backup handling, and owner-approved periods remain required before public use.

### Open release blockers and next actions

1. Obtain human labels for complete development and held-out video candidate sets. Keep held-out labels untouched while diagnosing errors/tuning on development labels, then run the evaluator and document limitations.
2. Select an owner-approved host, region, VPN boundary, privacy policy, retention periods, incident contact, and backup destination. Verify the actual firewall/origin boundary and approve recovery targets.
3. Produce a complete hash-locked dependency set for the chosen Linux/Python platform, run the hosted CI workflow on that exact install, and confirm security scans and cold/warm load checks there before release approval.

### Reproduction commands used in this workspace

From the repository root in PowerShell (replace the interpreter path with the active Python 3.14 executable on another machine):

```powershell
$py = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
$env:HF_HUB_OFFLINE = '1'
& $py -m unittest discover -s tests -v
& $py -m compileall -q backend frontend tests
& $py -m pip check
git diff --check
& $py -m backend.services.offline_evaluation --labels docs\recommendation-labels.csv --output artifacts\recommendation-evaluation.json --k 5
& $py -m backend.services.benchmark_recommender --db admind.db --title 'How to use Python for data analysis' --iterations 10

# Read-only source DB: backup, verify, restore to a new path, verify again.
$base = Join-Path $env:TEMP ("admind-recovery-" + [guid]::NewGuid().ToString("N"))
$backup = "$base-backup.db"
$restore = "$base-restore.db"
& $py -m backend.services.sqlite_backup backup --source admind.db --output $backup
& $py -m backend.services.sqlite_backup verify --database $backup
& $py -m backend.services.sqlite_backup restore --backup $backup --output $restore
& $py -m backend.services.sqlite_backup verify --database $restore

# Security scans use the isolated tools installed for this audit.
$env:PYTHONPATH = "$env:LOCALAPPDATA\Temp\admind-security-tools"
& "$env:LOCALAPPDATA\Temp\admind-security-tools\bin\ruff.exe" check --select E4,E7,E9,F backend frontend tests
& "$env:LOCALAPPDATA\Temp\admind-security-tools\bin\bandit.exe" -r backend frontend -ll
```

For a disposable API load run, start Uvicorn in one shell with a fresh temporary `DB_NAME`, `ADMIND_ENV=development`, `HF_HUB_OFFLINE=1`, and `--host 127.0.0.1 --port 8767 --workers 1`. In a second shell run `& $py -m backend.services.local_load_test --port 8767 --requests 4 --concurrency 4 --mode valid --pid <API_PID>`, then stop only that Uvicorn process. The temp database and process used for this verification were removed/stopped; the measured result above is retained here.

## Production-readiness follow-up (2026-10-20)

**Status remains NOT READY for production.** This follow-up preserves existing project data and leaves all source labels and privacy/hosting decisions unchanged. No rank weights, public infrastructure, production database, DNS, firewall, or public service were changed.

### Labeling packet and reviewer workflow

- `docs/recommendation-labels.csv` still contains 12 videos / 120 pairs, 120 `pending`, zero ratings, and no provisional labels. There were no AI-generated judgments to separate from human-reviewed judgments.
- Improved `backend/services/labeling_review.py` to embed a video only when a separate packet copy carries an HTTPS YouTube URL, verification status, verifier/date, and verification source. It renders the actual ad name, description, category, and mode for every candidate in the grouped set; it contains no ranking scores or order cues. The embed URL is constructed from a validated YouTube host and ID, and metadata is rendered with `textContent`.
- A subsequent source audit revised the earlier eight-match claim: four candidate URLs now have official metadata corroborating exact title/channel/date; four remain uncertain and unembedded. Three records remain without any URL, while the EMMA candidate conflicts with the packet's 2020 date and is not substituted. See `docs/recommendation-video-source-matches.md` for evidence and manual procedures. Even metadata-confirmed URLs still require footage confirmation.
- Created separate `artifacts/recommendation-labels-human-review.csv` and `artifacts/recommendation-human-review.html`; the earlier generated artifacts were preserved. The new reviewer groups all 120 pairs with split, stable video key, complete candidate count, video/source evidence notes, actual ad metadata, rating controls, and notes. Development and held-out CSVs export separately. The evaluator rejects missing IDs, duplicate pairs, invalid/missing ratings, split changes, and incomplete candidate sets. Held-out results are sealed unless a frozen ranker version is explicitly supplied. No ratings were generated.
- The HTML and CSV generation passed validation, but iframe playback/layout has not been visually verified in a browser. The earlier generated review HTML still reflects the previous eight-link claim; use the new human-review artifact for review.
- The in-app browser could not be initialized because its bridge rejected the missing `sandboxPolicy` field. The HTML output and its generation were tested, but iframe playback/layout was not visually verified in a browser.

### Privileged routes and access boundary

- Enumerated FastAPI routes: `/`, `/docs`, `/docs/oauth2-redirect`, `/openapi.json`, `/redoc`, `/health`, `/readyz`, `/livez`, and `POST /recommend-ad`. There are no admin API routes. `/recommend-ad` is intentionally public in the documented product contract; health/docs routes expose no admin operation.
- The Streamlit admin page is a UI-only privileged surface: its login uses PBKDF2 password verification, the page itself checks `admin_logged_in`, and production configuration fails closed without admin credentials. The checked-in Nginx example places the dashboard/admin hostname behind `allow`/`deny`, binds both app processes to loopback, and keeps the API on a separate hostname.
- This is configuration intent only. `nginx` is not installed in this workspace; no final CIDR/domain/certificate/firewall is selected; no proxy config test, external VPN/non-VPN test, or direct-origin reachability test was possible. The example VPN CIDR is a placeholder. Do not claim an enforced proxy boundary until the host-specific checklist records those tests.

### Privacy decisions and hosting checklist

- `docs/owner-decisions.md` remains the owner decision sheet. All proposals remain explicitly **Awaiting approval**: video metadata/history 30 days, raw events and feedback 90 days, request logs 30 days, encrypted daily off-host backups with 30-day expiry, RPO at most 24 hours, and RTO within four hours. Hosting region/jurisdiction, admin boundary, and incident/privacy contacts also await owner selection. No retention is enabled by this sheet.
- `docs/hosting-verification-checklist.md` remains unchecked and covers durable local storage, network/firewall/TLS, resource limits, monitoring, backup/restore, rollback, and release gates. No hosting item is represented as live-tested.

### Dependency lock and CI

- Corrected the lock input to resolve the pinned Python 3.14 set from `requirements-linux-py314.in`, added pinned `pip-tools==7.5.2`, regenerated `requirements-linux-py314.txt` with hashes, and changed README installation guidance to use `pip install --require-hashes -r requirements-linux-py314.txt`.
- A clean Python 3.14.3 Windows virtual environment installed the full lock using `pip install --require-hashes`; `pip check` passed. To check Linux wheel availability/hash coverage, ran `pip download --only-binary=:all: --require-hashes --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --python-version 3.14 --implementation cp --abi cp314 --abi abi3 -r requirements-linux-py314.txt`; it downloaded the complete Linux wheel set successfully. This validates resolved artifacts and hashes for the selected Linux platform tags, but it is not an installation or test run inside Linux.
- Reviewed `.github/workflows/quality.yml`; added `workflow_dispatch` and retained evaluation JSON as an Actions artifact. The workflow covers locked install, tests, compile, `pip check`, pip-audit, Bandit, Ruff, whitespace validation, and offline evaluation.
- Hosted CI was not run. `gh` is absent; the available session has no GitHub workflow-dispatch credentials/tool; local changes are not on a hosted runner. Triggering it would require pushing or a credentialed dispatch of these changes, and push is explicitly prohibited for this task. The local Git remote is read-only for this task.

### Cold-start measurement

Added stage timers to `EmbeddingService` and `VectorStore`. On the local Windows host, Python 3.14.3, offline cached `all-MiniLM-L6-v2`, 30 catalogue ads, and 537 source titles:

| Measurement | Result |
|---|---:|
| First complete recommendation | 16,978.95 ms |
| Embedding model load | 12,606.02 ms |
| Dataset read/prepare | 34.98 ms |
| Batch title encoding | 15,977.27 ms (includes model load; nested, do not add to model load) |
| Normalization and index build | 4.06 ms |
| Process RSS after cold request | 608.8 MB |
| Warm calls (10) | median 72.64 ms; maximum 123.76 ms |

This is a local single-process microbenchmark, not concurrent warm latency, Linux behavior, a production SLO, or capacity evidence. The earlier four-simultaneous-cold API run (4/4 HTTP 200, 29.87 s total, peak API RSS 644.3 MB) remains the only concurrent sample; public capacity is still unknown. No speculative optimization or ranking-weight change was made.

### Final local verification

Executed from the fresh locked environment with `HF_HUB_OFFLINE=1`:

| Command/check | Result |
|---|---|
| `python -m pip install --require-hashes -r requirements-linux-py314.txt` | Pass in clean isolated Windows Python 3.14.3 environment |
| `python -m pip check` | Pass: no broken requirements |
| `python -m unittest discover -s tests -v` | Pass: 31 tests |
| `python -m compileall -q backend frontend tests` | Pass |
| `ruff check --select E4,E7,E9,F backend frontend tests` | Pass: all checks passed |
| `bandit -r backend frontend -ll` | Pass: 2,933 lines; zero issues |
| `pip-audit --local` | Pass: no known vulnerabilities in the locked environment |
| `git diff --check` | Pass; only line-ending notices |
| Offline evaluator against original CSV | `awaiting_labels`; 12 videos, 120 pending, zero rated, metrics null |
| Linux target wheel download with hashes | Pass for manylinux 2.28 / manylinux2014, CPython 3.14 and abi3; not a Linux install |

### Remaining release blockers and required decisions

1. Human reviewers must confirm the eight embedded sources, supply verified URLs for the three unresolved titles and decide whether to exclude the conflicting EMMA record, then label complete candidate sets. Keep held-out labels out of tuning.
2. Owner approval is still required for all retention periods, backup expiry, RPO/RTO, hosting provider/region/jurisdiction, VPN CIDR or identity-aware proxy, incident/privacy contacts, and backup destination/key custody. Publish the privacy notice and configure the approved policy before public collection.
3. A deployment operator must configure and test the actual VPN/proxy/firewall/TLS boundary, durable storage, resource limits, monitoring, encrypted scheduled backups, timed restore, and rollback using the hosting checklist.
4. After these local changes are committed through the normal review path, run the updated hosted workflow on its Linux runner. The wheel check passed, but actual Linux installation/tests and hosted CI remain unverified.
5. Define acceptable cold/warm latency and measure both services together on the selected host under representative concurrency before setting a capacity target.

No deployment, public exposure, production-data modification, label inference, or ranking-weight change was performed.

## Labeling workflow follow-up (2026-10-20)

- Preserved all pre-existing worktree changes and generated files. `docs/recommendation-labels.csv` remains unchanged: 12 video keys, 120 unique pairs, all pending, zero ratings. The new `artifacts/recommendation-labels-human-review.csv` is a separate 120-pair copy, also all pending with zero ratings. `artifacts/recommendation-human-review.html` renders all 12 full sets with split, stable key, source context, ad names/descriptions/categories/modes, rating controls, and notes.
- Corrected source evidence: four of eight candidate URLs have official YouTube result metadata corroborating title/channel/date (Dani / Show Music Romania, WSJ, New Travel Insight, Edureka). Four candidate URLs remain uncertain and are unembedded. Three records still lack a source URL; EMMA has a 2025 similarly titled result conflicting with packet date 2020-10-21. Exact missing evidence and safe manual checks are in `docs/recommendation-video-source-matches.md`. Metadata confirmation does not establish footage identity.
- Reviewer exports separate development and held-out CSVs. Evaluator now validates identifiers, unique video/ad pairs, integer ratings 0–3, rated rows missing a score, reference-packet pair completeness, and unchanged split membership. Default output hides held-out label distributions and per-video completeness; a separate explicit flag plus frozen ranker version is required to expose held-out metrics/examples. Ranking code/weights were not changed.
- Final reviewer-generation command: `python -m backend.services.labeling_review --input artifacts/recommendation-labels-human-review.csv --manifest docs/recommendation-labels.csv --output artifacts/recommendation-human-review.html` — 12 video groups, 120 pairs, zero labels changed.
- Final evaluator command: `python -m backend.services.offline_evaluation --labels docs/recommendation-labels.csv --packet docs/recommendation-labels.csv --output artifacts/recommendation-evaluation-labeling-check.json --k 5` — `awaiting_labels`, 12 videos, 120 pairs, 0 rated, 120 pending, 0 complete development sets, null metrics, no inferred labels, held-out metrics sealed.
- Verification: `HF_HUB_OFFLINE=1 python -m unittest discover -s tests -v` — 39 tests passed; `python -m compileall -q backend frontend tests` passed; `python -m pip check` passed; `git diff --check` passed. Ruff and Bandit were not rerun for this continuation: the configured executables under the prior audit's `%LOCALAPPDATA%\Temp\admind-security-tools` location returned access denied from the current sandbox, and neither module is installed in the active Python environment. The earlier audit's scans predate these evaluation changes.

### Remaining labeling blockers

Obtain human review of the four uncertain candidate URLs and footage confirmation for the four metadata-confirmed candidates. Obtain original IDs/URLs and resolve title/date/footage for TeaserCon, The Audio Culture Academy, ShortsBreak, and EMMA Fitness; do not substitute similar titles. Then label every candidate in each video set without showing held-out ratings to ranking/tuning contributors. No recommendation-quality claim is supported until independent human labels are evaluated.

## Ruff and Bandit follow-up (2026-10-20)

This entry supersedes the previous note that these scanners could not be rerun. No `pyproject.toml`, `ruff.toml`, `.ruff.toml`, `.bandit`, `bandit.yaml`, `bandit.yml`, `setup.cfg`, or `tox.ini` exists in the repository. The effective Ruff configuration is the CI command in `.github/workflows/quality.yml`; Bandit has no repository-specific config/exclusions and CI invokes its default recursive scan.

The active project Python 3.14.3 environment and `.venv-ci-check` did not contain Ruff or Bandit, and no project venv was present. To avoid changing app dependencies or the production lock, installed only the pinned development tools into a fresh temporary environment under `%TEMP%`:

```powershell
python -m venv $env:TEMP\admind-ruff-bandit-<unique>
<tools-env>\Scripts\python.exe -m pip install ruff==0.17.1 bandit==1.9.4
<tools-env>\Scripts\python.exe -m ruff check --select E4,E7,E9,F backend frontend tests
<tools-env>\Scripts\python.exe -m bandit -r backend frontend -ll
```

Results: Ruff 0.17.1 reported `All checks passed!`; Bandit 1.9.4 on Python 3.14.3 reported no issues, with 3,009 lines scanned, zero skipped files, and zero skipped potential issues. The test suite was rerun: 39 passed. `git diff --check` passed. No source code, production requirements, or lock files were changed during this scanner-verification follow-up. The environment is isolated under the OS temp directory, outside the repository.
