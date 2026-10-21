# AdMind owner decision sheet

**Status: every proposal below is awaiting explicit owner approval.** No retention job, backup schedule, or recovery target is enabled by this sheet.

Use `Approve`, `Change`, or `Defer` for each row. Add the decision owner and date. Apply no database retention or host log/backup expiry until approved and reflected in the public privacy notice and operator configuration.

| Decision | Proposed starting point | Owner decision | Owner / date |
|---|---|---|---|
| Video metadata (`video_title`, category and related context in history) | Keep 30 days with the associated history row; avoid storing fetched descriptions unless separately justified. | Awaiting approval | |
| Recommendation history and session UUID | Delete after 30 days. No account mapping currently exists for user-scoped export/deletion. | Awaiting approval | |
| Raw analytics events | Delete after 90 days; preserve event-derived aggregate counts, subject to review of legacy aggregate behavior. | Awaiting approval | |
| Feedback | Delete after 90 days. | Awaiting approval | |
| Application request logs | Retain 30 days in journald; do not log request bodies, titles, or client IPs. | Awaiting approval | |
| Encrypted backups | Daily encrypted off-host copy, 30-day expiry, with access and key custody separated from the application host. | Awaiting approval | |
| Recovery point objective (RPO) | At most 24 hours of lost writes after a recoverable host/data incident. | Awaiting approval | |
| Recovery time objective (RTO) | Restore service within 4 hours after a recoverable host/data incident. | Awaiting approval | |
| Hosting region and jurisdiction | One Linux VM, one local persistent SQLite writer, region selected for policy and user geography. | Awaiting approval | |
| Admin access boundary | VPN CIDR or identity-aware proxy; dashboard/admin denied to all other networks. Public recommendation API remains separate and unauthenticated unless its product contract changes. | Awaiting approval | |
| Incident and privacy contact | Named operational and privacy contacts with a reviewed response path. | Awaiting approval | |

## Review notes

- These periods are proposals, not current policy or legal advice. They are not wired into automatic cleanup.
- SQLite retention only removes live rows. Backups keep deleted rows until backup expiry; event deletion reduces raw events while preserving aggregates according to current code.
- There is no user identity in the schema. Decide whether to avoid storing linked records or design an account/deletion mechanism before promising individual access or deletion.
- The service uses YouTube Data API for title/tags when configured, Google Fonts in the browser, and may fetch the embedding model from its model host. Review those data flows and user disclosures for the chosen deployment.
- Approving RPO/RTO requires a scheduled, encrypted, off-host backup and timed restore drill. The local SQLite round-trip does not establish either objective.
