**BLUESTAQ LIMITED** | Audit Logging Overview

# Audit Logging Overview

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the edition this one replaces)
**Version:** 0.3
**Last updated:** 2026-10-14

> **STRATEGIC SIGNIFICANCE**
>
> Every state-changing action is recorded in a tamper-evident chain. A retrospective edit, whether through the application, the database or direct disk access, is detectable by recomputing the hash chain, which `python -m app.cli.verify_audit` does, unless whoever made the edit also recomputed every later hash (section 03). The audit log is the load-bearing trust artefact for the whole system.

**SECTION 01**

## Intent

Every state-changing action in Holly is recorded in a tamper-evident audit trail. An investigator can replay the trail end to end, and a retrospective edit is detectable by recomputing the hash chain, within the limit in section 03. Reads are not recorded: viewing a page, listing records, downloading a procedure or exporting the shift log writes nothing.

**SECTION 02**

## Schema isolation and append-only enforcement

The audit log lives in its own PostgreSQL schema (ADR-005):

● Schema: `audit`
● Table: `audit.audit_log`
● Enforcement: the statement-level trigger `audit_log_append_only` runs `audit.refuse_change()` before any UPDATE, DELETE or TRUNCATE on the table and raises `audit.audit_log is append-only` (migration `0017_audit_append_only`).

ADR-005 recorded INSERT-only permissions, but no migration ever granted or revoked a privilege. Holly's own database user runs the migrations and owns the table, so the protection is the trigger, not a permission (ADR-012). The owner can still disable the trigger deliberately; the hash chain then detects a change made that way, within the limit in section 03.

**SECTION 03**

## Hash chain mechanism

Each row carries two hash columns:

● `previous_hash` is the `entry_hash` of the immediately prior row, or null for the first row.
● `entry_hash` is the SHA-256 of `previous_hash` followed by the canonical JSON of the payload, hex-encoded.

The payload is built from the row's own stored fields ([src/app/services/audit.py](../../src/app/services/audit.py)):

```json
{
  "action_type":  "...",
  "entity_type":  "...",
  "entity_id":    "...",
  "user_id":      "...",
  "ip_address":   "...",
  "detail":       { ... },
  "timestamp":    "..."
}
```

Canonicalisation rules:

● `json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)`.
● Keys are alphabetically ordered.
● No whitespace.
● Values JSON cannot hold (UUIDs, datetimes) fall back to `str()`. The stored `detail` text goes through the same fallback, so parsing it back reproduces exactly what was hashed.
● `timestamp` is the row's stored `timestamp`, in ISO 8601 form.

Because every input is stored in the row, anyone with read access to the table can recompute every hash. To verify the chain, walk the table by `timestamp` ascending, check that each row's `previous_hash` equals the prior row's `entry_hash`, and recompute each `entry_hash`. A mismatch points to an edited row, a deleted row or an inserted one.

> **LIMIT**
>
> The hash uses no secret key, and nothing outside the table records the latest `entry_hash`. Someone able to write to the table, with the trigger disabled, could edit a row and recompute every later hash, and the chain would still verify. The chain detects edits made without that recomputation. A copy of the latest `entry_hash` kept outside the database would expose a rewrite of any row before it; Holly keeps no such copy today.

> **NOTE**
>
> Rows written by the Daily Operations Dashboard, before Holly V0.2, hashed a timestamp that was never stored, so they cannot be recomputed ([src/app/cli/verify_audit.py](../../src/app/cli/verify_audit.py)). A chain that starts with such rows reports its first row as the break.

**SECTION 04**

## Verifying the chain

Run the verification command anywhere the database settings are available: inside the running container, or on a developer machine against a local database.

```sh
python -m app.cli.verify_audit
```

It reads `audit.audit_log` in timestamp order, recomputes every row, and prints one line:

```
Audit chain intact: <n> entries verified.
```

with exit status 0, or, on standard error with exit status 1:

```
Audit chain broken at entry <i> of <n>: id <row id>, <timestamp>, <action type>.
```

On a developer machine, run it from the repository root as `PYTHONPATH=src .venv/bin/python -m app.cli.verify_audit`. On the App Store it needs a shell in the running container; whether the platform offers one is `TBC, re-verify`.

**SECTION 05**

## Concurrency control

If two writers ran at the same moment, both could read the same latest `entry_hash` and write two rows that claim it as their predecessor, forking the chain. The audit writer prevents this with a PostgreSQL advisory lock taken inside the transaction (ADR-008):

```python
await db.execute(
    text("SELECT pg_advisory_xact_lock(:k)"),
    {"k": AUDIT_ADVISORY_LOCK_KEY},
)
```

`pg_advisory_xact_lock` is released when the transaction commits or rolls back, so the lock lasts no longer than the write it protects. After taking the lock, Holly sets the row's timestamp to the later of its own clock and one microsecond after the newest row's, so the chain's timestamp order, which the verifier walks, is its write order even when two containers' clocks differ or a clock steps back.

The key (`0x4F505841` in [src/app/services/audit.py](../../src/app/services/audit.py)) is constant across the application. Anything else that needs its own lock must use a different key; the migrations use `0x484F4C4C`.

**SECTION 06**

## Action type taxonomy

Action types are dotted strings, `<domain>.<entity>.<verb>` where that fits. Every value Holly writes today:

| Action type | Written when | `detail` carries |
|-------------|--------------|------------------|
| `auth.user.login` | Every sign-in attempt, except one refused by the per-address limit or because sign-in is busy (HTTP 503). | `success`; the `username` on success, and on failure only when it names an account; and on failure a `reason`: `unknown_user`, `inactive_user`, `wrong_password` or `rate_limited`. `user_id` is null when the username names no account. |
| `auth.token.refresh` | Every refresh-token exchange. | `success`, and on failure a `reason`: `invalid_token`, `malformed_subject`, `revoked_token` or `inactive_user`. On success the old refresh token's JWT ID (JTI) joins the `revoked_jti` block-list. |
| `auth.user.logout` | Every sign-out (`POST /api/v1/auth/logout`, refresh token in the body). | `success`, and on failure a `reason`: `invalid_token`, `malformed_subject` or `already_revoked`. |
| `auth.user.admin_upsert` | `python -m app.cli.create_admin` creates or resets an admin. | `username` and `action` (`created` or `updated`). No user id or address. |
| `udl.notification.ingest` | A notification pull: the hourly cycle, **Pull from UDL**, or `POST /api/v1/notifications/ingest`. | The request (`msg_type`, `created_at_gte`, `data_mode`, `source`, `max_results`) and the counts `pulled`, `inserted`, `updated`, `skipped`. |
| `udl.maneuver.ingest` | A manoeuvre pull by the background loop. | `event_start_time_gte`, `sat_no`, `data_mode`, `max_results` and the counts. |
| `udl.elset.ingest` | `POST /api/v1/elsets/ingest`. | `epoch_gte`, `sat_no`, `data_mode`, `max_results` and the counts. |
| `mattermost.ingest` | A Mattermost pull that polled at least one channel or failed one. | `channels_polled`, `channels_failed`, `pulled`, `inserted`, `skipped`. |
| `assistant.evaluate` | An evaluation: on demand (`POST /api/v1/assistant/evaluate/{id}`), or by the background cycle with no user id or address. A request for a notice whose classification marking is not cleared is recorded too, with `had_error` true. | `evaluation_id`, `model`, `procedures_used`, `had_error`; a background row also carries `trigger` (`background`). |
| `assistant.event_summary` | Each event narrative the background cycle attempts, in the same transaction as the narrative. Entity type `event`, entity id the event key; no user id or address. | `trigger` (`background`), `publications` (the number of the event's cleared publications), `had_error`. |
| `procedure.upload` | A procedure upload. | `name`, `filename`, `size_bytes`. |
| `procedure.delete` | A procedure deletion. | `name`, `filename`. |
| `shift_log.note.create` | A new shift-log entry. | `shift_date`, `had_error` (whether the polish failed). |
| `shift_log.note.update` | An entry's text is edited. | `shift_date`. |
| `shift_log.note.repolish` | An entry is polished again. | `had_error`. |
| `shift_log.note.delete` | An entry is deleted. | `shift_date`. |
| `shift_log.summary.generate` | An end-of-shift narrative is generated. | `shift_date`, `note_count`, `had_error`. |
| `event_timer.create` | A timer is set. | `label`, `event_key`, `target_time`, `pre_alert_minutes`, `recurrence`. |
| `event_timer.acknowledge_pre_alert` | A timer's pre-alert is first acknowledged. | `label`. |
| `event_timer.dismiss` | A one-off timer is dismissed. | `label`, `target_time`. |
| `event_timer.roll_forward` | A recurring timer is dismissed and moves to its next occurrence. | `label`, `recurrence`, `previous_target`, `next_target`. |
| `event_timer.delete` | A timer is deleted. | `label`. |

Not recorded: reads of any kind; and the analyst behind **Pull from UDL**, whose pull, evaluations and narratives are recorded as the cycle's, with no user id. Add a new action type to this table when it is introduced.

**SECTION 07**

## What gets recorded

For every audit row:

● **`action_type`**: see the taxonomy above.
● **`entity_type`** and **`entity_id`**: what the action acted on, for example `user`, `procedure`, `shift_note`, `shift_summary`, `event_timer` or `notification` with its id, or `event` with its event key. Ingest runs use `elset_ingest_run`, `notification_ingest_run`, `maneuver_ingest_run` or `mattermost_ingest_run`, with no id, because the action is bulk.
● **`user_id`**: the signed-in user, taken from the access token's subject. Null for the background loops, the admin command, and sign-in, refresh and sign-out attempts that name no valid user.
● **`ip_address`**: the client address the server saw (`request.client.host`). Behind the platform ingress this is the ingress's address unless gunicorn is set to trust its forwarded headers (`FORWARDED_ALLOW_IPS`); whether the platform does so is `TBC, re-verify` ([src/app/core/net.py](../../src/app/core/net.py)).
● **`detail`**: JSON text with the action-specific fields above.
● **`timestamp`**: the time Holly wrote the row, in UTC, or one microsecond after the previous row's when that is later (section 05).

**SECTION 08**

## Reading the audit log

### Through the dashboard (operators and admins)

`GET /api/v1/audit` returns audit rows newest first, a page at a time. It requires the `operator` or `admin` role; an analyst receives HTTP 403. Query parameters: `action_type`, `user_id`, `since`, `until`, `limit` (1 to 500, default 50) and `offset`. The dashboard's **Audit log** page, shown in the side navigation only to operators and admins, filters by action type and pages through 50 rows at a time.

### Direct database access (investigators)

Where a database shell is available (on the App Store, `TBC, re-verify`):

```sql
SELECT timestamp, action_type, entity_type, detail
  FROM audit.audit_log
 ORDER BY timestamp DESC
 LIMIT 100;
```

To check integrity, use `python -m app.cli.verify_audit` (section 04) rather than recomputing hashes by hand.

**SECTION 09**

## Exports

There is no audit export utility and no export action type. To take a copy for review, query the table directly (section 08).

**SECTION 10**

## Backups

Audit data is part of the PostgreSQL database, which the App Store POSTGRESQL add-on provides. Backup frequency and retention for the add-on are `TBC, re-verify`.

**SECTION 11**

## Open items

● Retention is undecided: every row is kept. Pruning old rows would need the append-only trigger disabled, and removing the oldest rows would leave the first remaining row pointing at a hash that is no longer present, which the verification command reports as a break. A retention design must account for both.
● The dashboard has no "verify the chain" control; `python -m app.cli.verify_audit` is the only verifier.
● Nothing anchors the chain outside the database, so a consistent rewrite of every later hash would verify (section 03).
● Rows written before Holly V0.2 cannot be verified (section 03).
● Whether the recorded `ip_address` is the analyst's or the ingress's depends on platform configuration: `TBC, re-verify`.
● The Mattermost loop writes a `mattermost.ingest` row every cycle while channels are configured: up to 1,440 rows a day at the default 60-second interval.

Bluestaq Limited | Holly documentation | 2026
