# Privacy and data lifecycle

This inventory reflects the current application code and local SQLite schema. Confirm it against the final hosting configuration before publication.

| Table.field | Purpose and use | Identifying / external flow | Retention, deletion, logs, and backup |
|---|---|---|---|
| `history.id` | Row key for dashboard history | No direct identifier | Same as history record; not logged; included in SQLite backup |
| `history.video_title` | Dashboard history and category/ad diversity context | Can reveal viewing interests; title is requested from YouTube API or manually supplied. Not sent to a paid model API; embeddings run locally. | No automatic expiry. `--history-days` dry-run/apply deletes it; no per-person mapping. Not written by request logs; included in DB backup. |
| `history.category`, `history.mode`, `history.ad_category` | Explain the video context and ad shown; session diversity | Not a person identifier; mode can reflect preference | Same history retention and deletion. Displayed in history/analytics UI; DB backup. |
| `history.session_id` | Scopes diversity to one browser session | Random UUID; linkable activity within a session, not linked to an account | Same history retention and deletion. Not in API request logs; DB backup. |
| `history.created_at` | History ordering and retention cutoff | Time metadata | Deleted with history row; DB backup. |
| `feedback.id` | Row key | No direct identifier | Same feedback retention; DB backup |
| `feedback.ad_name`, `feedback.feedback`, `feedback.created_at` | Ad-level positive/negative aggregate signal and timestamp | Not video-scoped or account-linked; may still reflect user preference | No automatic expiry. `--feedback-days` dry-run/apply deletes rows. Not included in API request logs; DB backup. |
| `analytics_events.id`, `event_id` | Row key and event idempotency | Random, opaque identifiers | Deleted with event row; DB backup |
| `analytics_events.request_id` | Associates an impression/click and deduplicates a recommendation event | Random request UUID; not joined to a user/session | No automatic expiry. `--events-days` dry-run/apply deletes; aggregate delta is subtracted. Not emitted in request logs; DB backup. |
| `analytics_events.ad_name`, `event_type`, `created_at` | Counts valid impression/click events for dashboard analytics | Ad/event/time, no identity | Same event cleanup. Ad-level totals remain in `analytics`; DB backup. |
| `analytics.ad_name`, `shown`, `clicked` | Aggregate counts; includes preserved legacy totals | Ad-level only, not per-user | Retained indefinitely; event cleanup subtracts only deleted event deltas. There is no deletion of legacy aggregate offsets. Included in DB backup. |
| `ads.ad_name`, `description`, `category`, `mode`, `created_at` | Catalogue identity and product description used for ranking | Product data, not user data; sourced from local catalogue | Retained until catalogue maintenance. Not request logged. Included in DB backup; catalogue source/version should also be retained. |
| API log `request_id`, `method`, `path`, `status_code`, `duration_ms` | Diagnose availability, latency, and HTTP errors | No request title/body or client IP; random trace ID | Host journal only. Configure `SystemMaxUse` and `MaxRetentionSec`; logs are not in DB backup. |
| Streamlit session `admin_logged_in` | Controls admin view after password verification | Transient session state, no persisted user identity | Expires with session; not logged or in DB backup. |
| `ADMIN_PASSWORD_HASH`, `STREAMLIT_SERVER_COOKIE_SECRET` | Admin password verifier and signed-session security | Secrets; never returned to a client | Inject from protected env/secret manager; not in DB backup and must not appear in logs. |

No user account or direct personal identifier is stored. Viewing title and session UUID are potentially sensitive/linkable data and should be treated as personal data for retention decisions.

Admin credentials are a PBKDF2 password hash in environment configuration, not a SQLite field; the logged-in flag is transient Streamlit session state. Neither is included in the SQLite backup. Configuration secrets must be backed up separately under secret-manager controls.

The dashboard currently uses Google Fonts from Google's hosted stylesheet, causing a browser connection to Google when the page loads. The YouTube Data API receives the video identifier in metadata requests when configured. The sentence-transformer model may be downloaded from its model host if it is not already cached. These are external services to disclose and review with the operator. No transcript is fetched or stored by this application.

## Operator workflow

Inspect counts first with `python -m backend.services.retention --history-days 30 --feedback-days 90 --events-days 90`. This is a dry run. The CLI also accepts `--older-than-days N` to apply one cutoff to all three record tables. Apply only after selecting policy and verifying a backup with `python -m backend.services.sqlite_backup verify --database PATH`; then repeat with `--apply`. Reports contain row counts and cutoff only, not titles or votes. The command is manual and is never called during ordinary startup. Applying it twice is idempotent. Backups contain the full database and require access controls and encryption at rest/off host; a deleted row can remain in backups until those copies expire.

## Conservative proposed starting periods (owner decision required)

- Recommendation history, including title and session UUID: 30 days.
- Feedback: 90 days.
- Raw analytics events: 90 days; aggregate ad counts retained unless policy requires a separate aggregate reset.
- Application request logs: 30 days in the host journal.
- Encrypted daily backups: 30 days, with longer retention only for an approved recovery/audit need.

These are proposals only. No cleanup is scheduled and no policy is approved. The CLI accepts separate periods for the three database row groups; host log and backup lifetimes must be configured independently.

The current schema has no user account or stable user identifier. Therefore, individual data export and deletion cannot be reliably fulfilled. Before collecting public-user data, decide whether to add an identity/account mechanism or avoid storing user-linked records, publish retention periods, and provide a support contact. Aggregate analytics may outlive individual event rows due to legacy data; review dashboard semantics before promising complete deletion of historic aggregate counts.

## Decisions required before launch

- Choose and document retention periods for history, feedback, analytics, application logs, and backups.
- Decide whether the service needs individual access/deletion requests; the current schema cannot map records to a person.
- Review YouTube API, Google Fonts, and model-host data flows and applicable notices/terms.
- Choose storage region, backup destination, encryption/key custody, and incident contact.
