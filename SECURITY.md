# Security positions

Holly's deliberate security positions and accepted risks, recorded rather than left silent (security-hardening). Each position names its trip-wire: the change that must revisit it.

## Accepted positions

| Position | Why it is acceptable now | Trip-wire |
|---|---|---|
| No authentication | Every route is a constant read that touches nothing; none costs money or changes state. | The first route that costs money or changes state lands with the constant-time team-token gate in the same change. `tests/test_app.py` holds the reviewed route inventory, so any new route fails until it is reviewed. |
| `/status` is public | It reports each input as set or not and its length, never a value, so a missing or stale input stays diagnosable without access. | Never add a field derived from a value. A secret joins `CONFIG_INPUTS` only if it is high-entropy, because its length becomes public. |
| No Cross-Origin Resource Sharing (CORS) middleware | With no allow-origin header, browsers refuse every cross-origin read: the fail-closed default. | The first cross-origin client arrives with an explicit `ALLOWED_ORIGIN`, and the app refuses to start on a wildcard. |
| No rate limiting | Every route is constant-time and touches nothing, and the health paths must never be throttled for the platform's probes. | The first expensive route lands with both limiter tiers, the health paths exempt, and the key taken from a trusted forwarded client address, not the ingress address. |
| `apt` and `dpkg` stay in the image | They need root, the image runs as uid 10001, and the platform's reference recipe keeps the OS package manager. | Remove them if the image policy scan flags them. |
| The upload content net has blind spots | It decides by content, not name: a file whose leading bytes mark an archive or compressed stream is refused whatever it is called, and every other file is scanned with the secret-scan hook's rules as UTF-8 and as UTF-16 in either byte order. Names add defence in depth (environment files, archive extensions and control characters, without regard to case). It cannot see a secret in a shape the hook has no rule for, such as an unquoted GitHub token or a JSON Web Token (JWT); in another encoding; or in a compressed stream embedded inside another format, such as a PDF, a Parquet file or an image. | Add rules for those token shapes to the shared hook list, through the Foundations baseline owner, before the first such credential exists. Refuse or unpack embedded formats before the upload first carries one. `scripts/test-package-nets.sh` pins every case the net does cover. |
| CI actions pinned by tag, not commit SHA | The workflow holds a read-only token and no secrets, and never deploys. | Pin full commit SHAs, each confirmed against the action's GitHub release page, before the workflow gains any secret or any write permission. |

## Relied on from the platform ingress

1. Host-based routing, so a forged `Host` header is never a routing decision inside the app.
2. Normalising or refusing a request that carries both `Content-Length` and `Transfer-Encoding`. The h11 server follows `Transfer-Encoding` and keeps such a connection open, where RFC 9112 asks for it to be closed.
3. Timeouts for slow clients. The app server held idle and trickling connections for 20 seconds and longer in review testing.
