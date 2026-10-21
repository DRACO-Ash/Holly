**BLUESTAQ LIMITED** | Changelog

# Changelog

**Data classification:** Unclassified (per ADR-006)
**Owner:** TBC, re-verify (the Daily Operations Dashboard Team, Bluestaq Limited, owned the history below)
**Version:** 0.12
**Last updated:** 2026-10-21

All notable changes to Holly are recorded here, newest first. Holly V0.2 is the Daily Operations Dashboard fused into the Holly App Store project and renamed; the sections after it are the Daily Operations Dashboard's own record, kept as written. Holly's releases are numbered V<major>.<minor>, and each has a row in `docs/AUDIT-LOG.md` with the checks that ran.

## Holly V0.12 (2026-10-21)

### Added

● **Holly finds its Mattermost channels itself.** Every minute it looks for every public and private channel the bot account is a member of, across its teams, and pulls new messages from the ones followed. A channel the bot joins is followed at once and named as new on the Comms page until someone marks it reviewed, so a new channel is never missed. Direct and group messages are never pulled.

● **Closed channels.** A channel archived in Mattermost, or with the word CLOSED in its name, in any case, yields nothing more than Holly has already pulled; taking the word out opens it again. A channel the bot leaves is shown as **Bot removed** and is not pulled.

● **The Comms console.** A channel list with a follow switch, a 24-hour activity chart on one shared scale, the count of messages new since your last visit and tags for each channel, the closed ones folded away with why they closed; a channel Holly does not pull says so rather than looking quiet. A **Feed** layout opens with the last 24 hours of every followed channel, a lane each, with a line at your last visit; below it every followed channel in one stream with search, a colour for each channel, a marker for what is new since your last visit, channels picked from the lanes or the list as removable chips, and newer messages offered rather than moving the list. A **Channels** layout shows one channel as a conversation that opens at your last visit and takes new messages as they arrive. **Find channels now** looks at once. Any signed-in user can change the follow list, for everyone, with an **Undo**, and each change is written to the audit log.

● **Help, beside Sign out.** The manuals in Holly, with their contents beside them, a section finder, links between the two manuals, and **Print or save as PDF**. Every signed-in user reads the analyst training manual; operators and admins also the operator manual, which the server refuses to anyone else (`GET /api/v1/manuals`, `GET /api/v1/manuals/{slug}`). The two Markdown files under `docs/` go into the upload and the image, so there is one copy of each, and the package nets require them. Holly reads them with its own small reader, which builds the page from the text and never as markup.

### Changed

● **`MATTERMOST_CHANNEL_IDS` is now a seed.** While Holly holds no channel they are still the channels pulled, and they arrive already reviewed on the first sweep that finds any. To have Holly read a channel, add the bot to it in Mattermost.

● **A rollback to V0.9 now asks for a new `APP_SECRET_KEY`** with the V0.9 upload, and again on any return to V0.10 or later: V0.9 checks no token version, so every session V0.10 ended would work again until it expired.

● **The documents catch up with V0.10:** the audit log's list of actions names the account actions, and the training manual's navigation names **Users** and **Password**.

● **The assistant panel's note for a notice kept from it.** A notice whose classification marking is not cleared for the assistant showed in red as "Assistant could not produce a structured evaluation". It is a decision of the disclosure control, not a failure, so the panel now says so calmly: the notice was not sent, its content stayed in Holly, and which markings the assistant may see is the data owner's decision (`ASSISTANT_CLEARED_MARKINGS`). The evaluation carries a `withheld` flag for it, and the panel offers no re-run, which could only give the same answer.

### Fixed

● **From the first review of Comms (ungated, so these await the gates):** a channel whose `type` is not text is skipped, where it stopped the sweep; the sweep is committed before the pull, so no channel row stays locked while Mattermost answers; any other failure fails the sweep in Holly's own words; a sweep that skipped a malformed record marks no channel lost, and says how many it skipped in the log and the audit row; a channel found already closed arrives reviewed; a seed the first sweep does not find is logged; a bot in more than 100 teams or 1,000 channels fails the sweep rather than store an unbounded list; a post holding a NUL, or anything else PostgreSQL cannot store, is skipped rather than stalling every later cycle at it; a nickname or channel name Holly cannot show gives way to the next; a Mattermost body nested too deep to decode is a client error, not a crash; `{"reviewed": 1}` is refused; channel ids go to the database as one array; the feed of followed channels asks by the follow list, so more than 200 followed channels no longer break it; a poll answered after the feed's scope changed is dropped; a failed read of the channel list clears once a later one succeeds; while Mattermost is not configured the page says Holly pulls nothing; and a search highlight no longer shifts after a letter such as "İ".

● **From the first security gate on V0.12:** the word CLOSED is read in each name as Mattermost sent it, before Holly cleans the names to show, with fullwidth and styled letters folded, every format, combining, enclosing, control and unassigned character read both as nothing and as a space, and a right-to-left name read reversed too, closing on any reading that holds the word (a look-alike letter from another script is an accepted gap in SECURITY.md), where a display name too odd to show (an emoji joined by a zero-width joiner, a tab) lost the word and the channel stayed open; any number in `delete_at` but 0 or below archives a channel, a float or NaN too; and a channel switched off or closed no longer reaches the assistant's prompt at once, rather than until its messages age out of the window. SECURITY.md records that the sweep's caps bound what is stored, not one listing's size.

● **From the first engineering gate on V0.12:** the feed and a channel's conversation no longer skip messages when more arrive between polls than one page holds (showing them reloads the latest page), and count them without the newest one already shown; an answer to an earlier ask (a search or scope since changed, older messages, an earlier read of the channel list, a channel no longer shown) never overwrites a newer one; the feed takes at most the 200 picked channels the server reads; the three layout and manual switches are fieldsets with a hidden legend, the highlight and activity bars are keyed by content, and the Markdown reader finds its marks without a backtracking pattern (SonarQube S6819, S6479, S4624 and S5852); a sweep that only skipped a record is audited; the smoke test checks the image serves both manuals; and the seed's wording matches the code everywhere.

● **The documents:** the seed's wording matches the code (it decides while Holly holds no channel), the operator manual warns that the first sweep follows every channel the bot is already in, the audit overview counts the rows a day, SECURITY.md records a bot added to a private channel by mistake, with its remedy, and the background loops' description names the sweep.

### Security

● **Three dependency advisories published since V0.11 are closed:** vite 7.3.6 to 7.3.7 (GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm, all in its development server's launch-editor), follow-redirects 1.16.0 to 1.16.1 under axios (GHSA-q3jh-wrc6-jgq8, GHSA-8r9p-f939-6h3c) and certifi 2026.7.22 to 2026.10.19 in the development lock only (PYSEC-2026-4320). Inference: none reaches the running image, since vite and certifi are build or test tools and the dashboard's axios uses the browser's request, not follow-redirects.

## Holly V0.11 (2026-10-20)

### Fixed

● **V0.10's upload failed the App Store's Code Quality stage** on two code smells (SonarQube S6819): the Users and Password pages announced their confirmations with `role="status"` on a paragraph. Each is now an `<output>`, the element that carries that role, and looks as before.

## Holly V0.10 (2026-10-20)

### Added

● **The Users page, for admins.** An admin creates accounts (a username of a to z, 0 to 9 and `. _ @ -`, an optional email, a role and a temporary password), resets a password to a temporary one, changes a role, and deactivates or activates an account. Each change is written to the audit log. An admin cannot change their own account there, and Holly always keeps one active admin. Until now, only the first admin could be created.

● **Password, for everyone.** Every user can change their own password, giving the current one and a new one of 12 to 1,024 characters, not spaces alone.

● **A temporary password must be changed.** A user whose password an admin set sees only the password page, at their first sign-in or after a reset, until they choose their own; Holly refuses everything else meanwhile.

### Changed

● **A password change, a reset or a deactivation ends the user's sessions.** Every token now carries its user's token version, and each of these raises it, so a token issued before stops working at once, on any device, even when a password change is running at the same moment. Your own change keeps you signed in where you made it. Tokens issued by V0.9 keep working until the first such change.

● **The operator manual records that the `/data` volume is writable by Holly's user,** as the platform team confirmed and V0.8 and V0.9 showed.

● **A refused request's message no longer gives the length of the value it refused,** so a password that is too short or too long is not described by its length.

## Holly V0.9 (2026-10-20)

### Fixed

● **On the App Store, signing in showed the dashboard and then returned to the sign-in page at once.** The platform's gateway answered with a refusal of its own, rejecting Holly's token in the `Authorization` header as one the platform did not sign; it most likely reads any bearer token there as the platform's (inference). The dashboard now sends Holly's token in its own header, `X-Holly-Token`, and Holly never reads `Authorization`. Scripts that call the API send `X-Holly-Token: <token>`, the token alone.

● **Reloading the page after the 30-minute access token had expired returned to the sign-in page,** even with a valid refresh token, because the dashboard never refreshed after its first call, `/auth/me`, was refused. It now refreshes once first, as for any other call.

### Changed

● **Holly's address is `https://holly.appstore.bluestaq.com`,** as the App Store serves it; the documents said `holly.apps.bluestaq.com`.

● **An origin listed in `APP_ALLOWED_ORIGINS` no longer gets credentials mode.** Holly reads no cookie, so a client on such an origin sends its token in `X-Holly-Token` without credentials; one that asked for credentials is now refused at its preflight.

## Holly V0.8 (2026-10-19)

### Fixed

● **V0.7's upload failed the App Store's DAST scan, which starts the container with none of Holly's settings.** Holly refused to start without its signing key and database, so the scan found nothing listening on port 8080. Under the scan's flag alone, Holly now fills in a throwaway signing key and a temporary store, turns its background pulls off, and serves without a database if the scan gives it none; a request that needs one answers 503.

● **Holly waits about a minute at start for a database it cannot reach,** instead of stopping at once, as the platform advises; a database that answers and refuses, such as one given a wrong password, still stops the start at once, now naming the refusal's code.

● **A code-quality finding in how the assistant panel keys its lists,** the one V0.7's upload failed Code Quality on. The loop that finds an unused key now tests and updates the same value (SonarQube S1994). The keys are unchanged.

## Holly V0.7 (2026-10-19)

### Added

● **The first admin comes from App Store variables.** Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` before the first start: Holly creates that admin at start while it holds no account and records it in the audit log. Once any account exists no value is checked or used, so none can reset a password or stop a start; remove them after the first start. Before then, half a pair, or a value Holly cannot store, stops the start with a message that names the variable and never its value. No shell in the container is needed.

● **The deployment's record.** The operator manual lists the app record as the App Store console shows it: the slug `holly`, port 8080, the health check on `/`, 4Gi of memory and 2000m of CPU, PostgreSQL 16 and the file store at `/data`. Withdrawing the app is removing it from the App Store.

### Fixed

● **An assistant deadline that is not a timestamp, or a time of day without its UTC offset, is dropped when the reply is checked,** so it is never stored; one already stored that is not in ISO 8601 form shows as written, without "By".

● **No failed database statement prints its bound values to the log,** in the application or its migrations, so an admin's password hash cannot reach it that way.

## Holly V0.6 (2026-10-19)

### Fixed

● **The 68 findings the App Store's Code Quality gate reported on V0.5's upload, which it failed.** V0.5 passed the test stage; the gate then listed 5 bugs, 2 vulnerabilities and 61 code smells, and each is fixed in the code it names.

● **Each notice on the dashboard is a link.** The whole item opened its notice on a click, with no way in from the keyboard; it is now one link to the notice, reached with Tab and opened with Enter, with the focus ring every control shows.

● **Sortable columns tell a screen reader how the list is sorted.** The sort order sat on the column's button, where assistive technology does not read it; it is now on the column header the list is sorted by.

● **The development servers listen on this machine only.** `python -m app` and the dashboard's Vite server bind 127.0.0.1; the container still listens on every interface, as the App Store requires.

● **The container installs Python packages from wheels only**, so no package's build step runs while the image is built, and its base images are named by digest alone.

● **Cross-Origin Resource Sharing (CORS) answers first.** Every response to an allowed origin carries its headers, a refusal for too many requests included; a preflight is answered before the security headers, the request id and the rate limit (SECURITY.md); no origin is allowed by default, as before.

### Added

● **Packaging records where the gate's window opens.** The App Store scores new code against the previous upload, passed or failed, and records that nowhere in this repository. `scripts/upload-baseline.txt` records each upload handed over, and packaging for upload refuses without it, prints the files that changed since, and refuses an upload that changed without a higher version.

## Holly V0.5 (2026-10-19)

### Fixed

● **Both of the App Store's test jobs failed on V0.4's upload; each now passes in a simulation of it.** The python job installs `requirements.txt`, then runs `pytest --cov --cov-report=xml:coverage.xml`, but that lock held only the runtime set, so pytest was not there to run. It now holds the runtime set and the test runner, and the image installs the runtime set alone, from the new `requirements-runtime.txt`, so no test tool reaches it. The node job runs `npm ci` at the upload's root, where V0.4 had no package to install. A root `package.json` and lockfile, holding no packages of their own, now hand the install, the tests and the build to the dashboard, which installs from its own lockfile with install scripts off.

### Added

● **The dashboard's code is tested, and held to 80% coverage.** Vitest renders every page, component and context in a simulated browser (jsdom, with Testing Library) and checks what an analyst sees and what each page sends to Holly's API, where 11.67% of the dashboard's lines were tested before. The tests write their coverage to `coverage/lcov.info` at the upload's root, naming each file as the platform finds it, and fail under 80%, the floor the platform's Code Quality gate holds an upload to. The test packages were locked so that none was younger than 15 days when added, and the image's build leaves the tests out.

● **The pipeline simulation runs both of the platform's test jobs**, each on its own fresh checkout of the upload, with the commands V0.4's job logs show, and fails if either fails. The node job's commands after `npm ci` follow the platform's node template until they are confirmed.

● **The loop holds the three Python locks to one set of pins**, each package at the same version, under the same marker and with the same hashes in every lock that carries it, so the platform's test job tests what the image ships, and it audits all three.

## Holly V0.4 (2026-10-19)

### Added

● **The dashboard ships the licence of every package in its build.** The build copies the licence text of each package with a module in its graph, or with a file the build reads, such as a font, a stylesheet an @import brings in, a file a url() inlines or a worker's code, to `licences/` beside the dashboard, served at `/licences/` with an index at `/licences/index.txt`: the three typefaces under OFL-1.1, eight more packages under MIT, and Vite, whose helper code is in the script. A package without a licence file, or code or a file from outside every package and Holly's own source, stops the build, and so does a file the page or a script's new URL() inlines with ?inline, which Vite writes into the output without recording that it read it. The verification loop checks that each runtime dependency's licence is there, and runs the plugin's self-test, which shows each of those stops still working.

### Changed

● **The dashboard wears the Holly design document's theme: CRT phosphor on bulkhead steel.** Phosphor green leads the eye, rust marks alerts and amber warnings. The header, the sign-in panel, the side navigation and the frame around each page are steel bulkheads, and each page sits on a CRT screen edged by a vignette. Headings, navigation, labels and buttons are set in Share Tech Mono, body text in Inter, and code and records in Fira Code. All three are bundled into the build as three pinned Fontsource packages (OFL-1.1), because the dashboard's policy allows fonts only from Holly itself. The header carries the document's bracketed wordmark, the sign-in page its plate logo, and the browser tab its square icon.

● **Each analyst can switch two screen effects from the header.** Scanlines start on: they texture the screen behind the text and cross the large readouts, the page headings and the dashboard counts. They never cross body text, where any visible strength would pull the fainter labels below the contrast floor. CRT flicker starts off, and stays still when the system asks for reduced motion. Both choices are kept in the browser only.

● **Every text, background and border colour is a token, and the loop holds the theme to WCAG AA.** The stylesheet's last hard-coded tints now derive from their tokens. `scripts/contrast-check.mjs` measures every text and field-edge pair the tokens make, the focus ring among the text, including tints over the chrome they sit on, the large readouts under the scanlines, the screen while it flickers and the firing banner at the peak of its pulse. It also refuses an accent closer than 0.2 in the OKLab colour space to a status colour; takes the flicker's depth from the one keyframes block its rule names, however the name is written, which may change opacity only; and refuses any colour a rule paints with outside the tokens, in each of the 60 property forms that paint one, with any vendor prefix or none, and any custom property defined outside them, since nothing would measure either. Text must be painted in a token, one outside the text tokens only on its rule's own background, and may sit only on a token or a tint of one, where the check measures it, with no background image or border image under it; transparent text, text that takes its parent's colour by keyword over a background of its own, a text fill other than a keyword, a background clipped to the text or through a token, the keywords that bring back the browser's own colours, a colour mix other than a tint, an easing that can carry a fade or a colour past its keyframes, and a colour scheme switched outside :root are refused. It reads the stylesheet as CSS does, so a comment opener or a brace inside a string hides nothing from it and a comment separates what it lies between, and refuses what CSS would read otherwise than it does: a backslash, a string its line ends before it closes, url(, a character outside printable ASCII outside a string or a comment, a brace or semicolon inside brackets, a block nested in a rule or never closed, an at-rule holding declarations beside blocks, a painting property or a token declared twice in one rule, background with background-color in one rule, an @import and an @property. Every form it passes was held against Chromium 141, among 803,418 generated, and the ones Chromium paints otherwise are the limits it names. Shadows and masks stay as decorative shading, and the check says what it cannot see, the cascade, opacity and filters among them. The loop runs its self-test: 376 forms it must refuse, each for the reason it names, or accept, each written where nothing later in the sheet overrides it, with a case for each entry of each list the check measures and for each property it holds to the tokens, every floor held from both sides, the stylesheet measured to the pair, and 5 views of what it reads. `scripts/mutation-battery.mjs`, which CI runs after the loop, removes or moves each control of the check and the licence plugin in a copy, and each entry of those lists and of the words the check allows, 484 mutants in all, and fails unless the case each names goes red; 13 more it declares equivalent must leave their self-test green.

● **The theme keeps the interface readable as well as styled.** Links are underlined, so colour is never their only cue. Code and records show their characters as stored, with the code face's ligatures off, and headings that show a record's value keep its case. Native controls, date pickers and autofill follow the dark theme. Focus shows as a phosphor ring on every control, checkboxes included, and the side navigation marks the current page for screen readers. A dismissed timer dims by colour, not by fading below the contrast floor.

### Fixed

● **A procedure's text was unreadable.** It was drawn in the light text colour on a near-white panel; it now sits on the screen colour in the code face.

● **Every signed-in page reflows on a narrow or zoomed screen.** The header wraps rather than squeeze whenever its brand and controls do not share a line, never shrinks under firing banners, so Sign out stays whole, and a username too long for the screen breaks. At 760 pixels and below a timer's buttons drop below its text; at 600 and below the side navigation becomes a row of links above the page; and on a window 600 pixels wide or 480 tall, or smaller, the whole page scrolls. The sign-in page scrolls rather than cut off its logo. A note's buttons, a message's header, the pager and the narrative's heading wrap, a long word in a timer's label breaks, form fields shrink to the screen, and the navigation scrolls when banners leave it short. At 320 by 256 pixels, a 1,280 by 1,024 window at 400% zoom, every page's content, every link and Sign out can be reached, and nothing scrolls sideways but a data table. On a window wider than 600 pixels and taller than 480, a few timers firing at once, from four with short labels or two with labels of 100 characters or more, and more on larger windows, can still leave the page no room until one is dismissed, which dismisses it for every analyst, much as in V0.3 (SECURITY.md).

## Holly V0.3 (2026-10-15)

### Added

● **Packaging for upload checks the binding reviews.** `scripts/package-appstore.sh` writes the upload only when the last verdict from each gate in the committed `scripts/upload-record.txt` is a PASS on a commit at or after the version bump whose upload and packaging are unchanged since. It packages the commit at the tip of a local branch that is not behind its upstream as last fetched, resolved once, refuses if HEAD moves meanwhile, refuses an upstream that is configured but does not resolve, a packaging tool that differs from its committed content and a zip that does not hold exactly the committed files, ignores git's local replace refs, grafts and textconv drivers, and first removes the last upload zip on every run. A branch with no upstream is not compared, and the run says so. The pipeline simulation and the container smoke package rehearsals into their own temporary files, so they still run before the reviews.

● **The upload refuses the agent configuration by name.** `scripts/check-package.sh` refuses `CLAUDE.md`, `CLAUDE.local.md`, `.mcp.json` and anything under `.claude/`, in any case and at any depth, whatever the path list in `scripts/package-appstore.sh` says.

### Changed

● **The container smoke rung tests against PostgreSQL 16.** The App Store's upload page lists the POSTGRESQL add-on as PostgreSQL 16, so `scripts/smoke-container.sh` now runs PostgreSQL 16.15, pinned by digest, in place of 15.19. It refuses a database image without that digest and logs the server version it tested, and the verification loop checks that both database images are pinned by digest and that the smoke rung refuses an image without its digest. The local database in `infra/docker-compose.yml` stays on 15.19, because a data volume made by 15 will not start under 16.

### Fixed

● **A refused name could pass the upload nets in another form.** `unzip` lists a DEL or a byte above 0x7E as it stands, or converted from CP437 in a UTF-8 locale, and an extractor may drop or change it: Info-ZIP drops a DEL, so `prod.en<DEL>v` passed every name check and landed as `prod.env`. Info-ZIP also strips a VMS version suffix, so `CLAUDE.md;1` landed as `CLAUDE.md`. Member names must now be printable ASCII without a backslash, every file must land under its listed name, and a `grep` error refuses rather than reading as no match.

● **The local database is ready when `--wait` returns.** `infra/docker-compose.yml` gives PostgreSQL a health check over TCP, so `docker compose up --wait` and `scripts/dev.sh` hold until the published port takes connections, and the verification loop checks that the health check asks over TCP and that `dev.sh` waits for it. Without it, `--wait` returned as soon as the container started; on a fresh volume nothing listens on TCP until the image has initialised the database, with initdb and then a temporary server on its Unix socket alone, so the migrations' first connection was reset.

## Holly V0.2 (2026-10-14)

### Added

● **One App Store container.** The React dashboard is compiled in the image and served at `/`, beside the API under `/api/v1`, the platform probes and a secret-free `/status`. Migrations run at container start in the gunicorn master, under a PostgreSQL advisory lock. One worker runs the background refresh, so it runs once.
● **Limits.** A coarse rate limit per client address on the API and `/status`; sign-in attempts limited per client address, before any password is checked, and checked sign-ins per username, each counted before its check so guesses sent together cannot pass the limit; at most 4 password checks at once, on worker threads, so a burst of sign-ins cannot stall the worker; assistant calls limited per user; a daily assistant token cap (`LLM_DAILY_TOKEN_CAP`) that fails closed and holds each call's largest possible cost before it is sent; request bodies capped at 256 KiB, 11 MiB for a procedure upload, whose form is read only after sign-in.
● **`ASSISTANT_CLEARED_MARKINGS`**: the UDL classification markings whose notifications, and the manoeuvre records sent with them, may be sent to the assistant, `["U"]` by default. Any other marking, or none, never leaves Holly; the dashboard says which notices were not sent. Each background evaluation and event narrative is written to the audit chain; once a sending may have gone, any failure to store it or its row stops that phase for the cycle.
● **`python -m app.cli.verify_audit`**, which recomputes the audit chain and names the first broken link. Migration 0017 refuses every UPDATE, DELETE and TRUNCATE on the audit log, the insert-only rule ADR-005 recorded but no migration enforced.
● **Recurrence anchor for event timers** (migration 0016): a monthly timer set for the 31st now returns to the 31st after a shorter month.
● **Unit tests for the dashboard's logic** (Vitest), and a server suite of 1,050 tests at 99% line coverage.
● **`scripts/dev.sh`**, the local run: PostgreSQL from `infra/docker-compose.yml`, migrations, the API on 8080 and the dashboard on 3000.

### Changed

● **Renamed to Holly**: the page title and header, the browser storage keys (`holly.*`, so every analyst signs in once more), the service name in the logs and the package names.
● **Settings are validated at boot and fail closed**: a signing key of at least 32 characters, no `*` origin, https for UDL and Mattermost outside development, and an absolute, writable procedure store (proved with a real write at boot). A refusal is one line that names each variable at fault and repeats no value. A `DATABASE_URL` is read once, by the parser that connects: it may carry libpq's `sslmode`, and only an `@` in its password, or a `%` before two hexadecimal digits, needs encoding.
● **Failed sign-ins**: the audit chain records the username only when it names an account, since an unknown one may be a password typed into the wrong box.
● **Assistant failures** reach analysts as fixed messages; the Anthropic API's own text stays in the server log.
● **Sign-in tokens use PyJWT** in place of python-jose, whose ecdsa dependency carries an advisory with no fixed release. Decoding accepts the configured algorithm only and requires every claim.
● **The audit chain hashes each row's stored timestamp and stored detail**, so every row Holly writes can be recomputed. Rows the Daily Operations Dashboard wrote hashed a timestamp it never stored and cannot be verified.
● **The admin command takes its password** from `ADMIN_PASSWORD` or a hidden prompt; the `--password` flag is gone, so a password never lands in shell history or the process list.
● **Downloads and exports** fetch with the analyst's token; the plain links before could not carry it.
● **Dashboard dependencies**: axios 1.20.0, react-router-dom 7.18.4, Vite 7, Vitest 4 and ESLint 10, exactly pinned; `npm audit` reports no known vulnerability.
● **The interactive API documentation is off**, and every response carries a strict Content Security Policy (a dashboard policy for the page itself), `nosniff`, `no-referrer`, `no-store` and a request id.

### Fixed

● Every uploaded procedure was stored in one file per extension, named after an id the row did not have yet, so a later upload replaced an earlier one's content and refusing a duplicate deleted the original's file. An upload that fails for any reason now removes its own file, a blank name is refused, and a download whose file is missing answers 404 instead of failing.
● A failed event narrative no longer replaces the earlier one and hides it: nothing is written, and the event is retried in the next cycle.
● Event summaries: a summary is refreshed only when the window holds a publication it has not seen, and from the event's full history, so it never shrinks as older publications age out; a timestamp tie no longer triggers a fresh narrative every hour; the newest events are summarised first when the per-cycle cap applies. The assistant is shown at most 20 publications of one event, the first and the newest, so a long-lived event costs no more to summarise than a busy one.
● The hourly loop survives a cycle cancelled by another caller, and stopping the loops no longer swallows the caller's own cancellation.
● A spent assistant limit no longer refuses a shift note: the note is kept as written and can be re-polished later.
● The dashboard did not compile as uploaded: `SortDirection` was imported in three files and defined in none.
● A failed re-polish no longer discards a note's polished text, including an analyst's own edit; a failed summary no longer hides an earlier good one.
● Mattermost: a malformed post is skipped and counted instead of aborting the run, or stalling every later run on the same post; an answer that is not a JSON object is a client error; ids are checked before they reach a request path.
● Satellite ids that UDL sends as numbers no longer crash evaluations and event summaries.
● Event timers: a whitespace-only label is refused, targets are bounded to the years 2000 to 2099, and an unknown recurrence value is dismissed once instead of looping. The pre-alert badge and browser notification give the timer's own lead time, not a fixed 5 minutes.
● A manual UDL ingest may ask for at most 10,000 records in one pull. The element-set ingest's audit entry now records the data mode it asked for.
● One UDL record that its table cannot store, such as text longer than its column, a NUL or lone surrogate in any text, NaN in its raw JSON, a number or time beyond its column's type, or an element that is not a record, no longer fails the whole pull: it is skipped, counted and logged by column.
● A model reply holding a character PostgreSQL cannot store is refused like any unusable reply, instead of failing the write after the call.
● Text holding a NUL is refused with 422 in every request body, upload and free-text query parameter. A shift note holding one was sent to the assistant before its write failed with a 500, and a NUL in a query or a sign-in answered 500. A 422 now names each field and its problem but never echoes the submitted value, which could be a password, and a lone surrogate in a JSON body gets its 422 instead of a 500.
● Each refused request built a new traceback onto one shared exception, so memory grew with every 401; each refusal is now a new exception.
● An upload whose file write fails part-way, or whose request is cancelled, no longer leaves a file behind.
● An assistant reply nested too deeply to read is an assistant error, not a crash that re-billed the notice every cycle; the parser tries at most 20 opening braces, so a crafted reply cannot hold the worker.
● Audit rows are timed after the newest row, so two containers whose clocks differ cannot make the verifier report a break.
● A failed download shows the server's message, such as a missing procedure file, not the bare status code.
● A 500 response carries the request id.
● Each evaluation read every previewable procedure file whole, up to 10 MB, for a 64 KiB preview; it now reads the preview only.
● The empty Comms page no longer tells analysts to edit a local `.env` file.
● Links from UDL records become clickable only for http and https, and every new-tab link carries `noopener noreferrer`.

### Removed

● The nginx configuration and certificates, the development Dockerfiles, `scripts/dev.ps1`, `.env.example` (`docs/developer/setup.md` lists every setting), the `/ws` development proxy, and the unused `EventSummaryRead` schema.

## Daily Operations Dashboard: [Unreleased]

### Added

● **`scripts\dev.ps1` one-file local deploy and run.** Idempotent: creates `.env` from `.env.example` with a fresh `APP_SECRET_KEY` if missing, generates a self-signed TLS certificate via docker if `infra/certs/` is empty, brings up the full stack, waits for the database, applies pending alembic migrations inside the backend container, bootstraps the first admin user if `app_user` is empty, and tails backend logs. Supports `-Down`, `-Restart`, `-Reset` (destructive), `-NoLogs`, `-RegenerateCerts`. Admin credentials can be supplied via `-AdminUsername`/`-AdminPassword` flags or `$env:ADMIN_USERNAME`/`$env:ADMIN_PASSWORD` for non-interactive runs.
● **Real TACREP_NOTSO shape support.** UDL nests the interesting fields inside `msgBody`; mapper now extracts `NOTSO` (notice identifier), `Event_Class`, `Event_Type`, `Event_Id`, `Status` (OPEN/CLOSED), `Event_Description`, `Company_Name`, `NOTSO_Link`, `Publish_Date`, and the `SatIds` array. Top-level envelope fields (`createdBy`, `origNetwork`, `classificationMarking`, etc.) are now captured too. Migration `0006_notif_msgbody` adds eleven new typed columns plus four query indexes (`notso_identifier`, `status`, `event_type`, `publish_date`).
● **Notifications page redesign.** List view now shows Notice / Status / Type / Event class / Sat IDs / UDL created. Status filter (OPEN/CLOSED), event-type filter, and status indicator pills. Ingest form defaults `Source` to `JCO` to match the production query.
● **Notification detail view.** New sections for Status, Identification (including the `NOTSO_Link` URL to the JCO source page), Timing, Associated objects (rendering the full `SatIds` array), Event description (preformatted), and Source artefacts (parses `NOTSO_Image_Metadata` and renders clickable links to the underlying assets).
● Single-sat convenience: when `SatIds` has exactly one numeric value, `sat_no` is populated so existing filter and sort paths still work; multi-sat notices populate `sat_ids` only.

### Changed

● `infra/docker-compose.yml` now mounts the repo root at `/workspace` on the backend container so alembic can find `alembic.ini` and `migrations/` (which live at the repo root, not under `backend/`). No effect on the production-time backend (uvicorn still runs from `/app`).
● `frontend/vite.config.ts` pins the dev server to port `3000` to match the `proxy_pass http://frontend:3000;` line in `infra/nginx/nginx.conf`. Previously vite defaulted to `5173` and the nginx proxy would have failed; fix went unnoticed because nobody had brought the full stack up locally yet.

● **`notso` → `notification` rename.** UDL serves Tactical Reports (TACREP) and Notices to Space Operators (NOTSO) through a single `/notification` endpoint under `msgType=TACREP_NOTSO`; the earlier naming treated them as separate surfaces, which was wrong. Alembic migration `0005_rename_notso` renames the table, its indexes, and the unique constraint. Backend model, schemas, ingest service, routes, UDL client method, and audit action type (`udl.notso.ingest` → `udl.notification.ingest`) all renamed accordingly. Frontend page, types, API wrapper, navigation label, and route URL move from `/notsos` to `/notifications`. UDL endpoint corrected from `/notso` to `/notification`. New ingest parameters (`msg_type`, `created_at_gte`, `data_mode`, `source`, `max_results`) match the example URL used in production. `msg_type` defaults to `TACREP_NOTSO`.

### Added

● **Observability and code-quality bar.** Every HTTP response now carries an `X-Request-ID` header (honoured from inbound or generated as a UUID), and every backend log line includes the active `request_id` so traces can be correlated end-to-end. New `GET /api/v1/health/detailed` returns a component breakdown (database connectivity, UDL credential configuration) plus version and environment. Coverage is enforced in CI via `pytest-cov` with a 40% floor (initial bar, will ratchet up). Frontend code is now governed by Prettier; a `format:check` step runs in CI alongside the existing eslint step.
● **Audit log viewer.** New `GET /api/v1/audit` endpoint role-gated to `operator` and `admin` via the existing `require_role` factory. Filters by `action_type`, `user_id`, `since`, and `until`; paginated. Frontend Audit log page shows timestamp, action, entity, user, IP, and the parsed detail payload. AuthContext now fetches `/auth/me` on mount and exposes the current `user`; Layout filters the side nav by role so the audit link only appears for operators and admins.
● **UI polish.** Sortable column headers on the Element sets and NOTSOs list pages (click to toggle direction, with an arrow indicator). Detail pages at `/elsets/:id` and `/notsos/:id` showing parsed fields, the TLE for elsets, the description for NOTSOs, and the full raw UDL payload. Rows in the list pages are clickable and route through to the detail. Dashboard refreshed with live count cards for each surface (Element sets, NOTSOs) including the most recent record's label and timestamp.
● Backend list routes now accept `sort_by` and `sort_dir` query parameters (whitelisted via `Literal` types, validated by FastAPI). Defaults preserve previous behaviour (elsets by epoch desc, NOTSOs by effective_from desc).
● Reusable `SortableHeader` component, design tokens for sortable headers, clickable rows, detail-grid, raw-json, TLE block, NOTSO description block, and the dashboard surface cards.
● **NOTSO ingest, end-to-end.** New `Notso` model and migration `0004_create_notso`, `UDLClient.get_notsos()`, `ingest_notsos` service mirroring the elset pattern, REST API at `/api/v1/notsos` (list with `msg_type` and `sat_no` filters, detail, and a manual ingest trigger). Frontend Notsos page with the same shape as Element sets. Action type `udl.notso.ingest` is now Active in the audit taxonomy.
● `UDLClient` factored to share a single `_get_list` helper between `get_elsets` and `get_notsos`. No behaviour change for the existing elset path.
● Backend tests for the NOTSO UDL-to-model mapping (full record, datetime parsing across `effectiveFrom`/`effectiveUntil`/`expirationTime`/`createdAt`, raw payload preservation, missing-id skip, fallback aliases for `text` and `expirationTime`).
● Refresh-token rotation and JTI block-list (ADR-011). Every JWT now carries a `jti` claim. `POST /auth/refresh` rotates: it issues a new access AND a new refresh token and revokes the old refresh-token JTI in the `revoked_jti` table. A reused old refresh token is rejected with audit reason `revoked_token`. New alembic migration `0003_create_revoked_jti` adds the block-list table. New `app/services/token_revocation.py` exposes `is_revoked` and `revoke`.
● `POST /auth/logout` now takes the refresh token in its body (no access-token header required) and revokes its JTI. The audit row carries success or one of `invalid_token`, `missing_claim`, `malformed_subject`, `already_revoked`.
● Audit-log emission for auth events. `POST /auth/login` writes `auth.user.login` rows for both success and the three failure modes (unknown user, inactive user, wrong password); `POST /auth/refresh` writes `auth.token.refresh` rows for success and the new revoked-token failure reason. Action types are Active in the audit taxonomy.
● Real JWT authentication. `POST /api/v1/auth/login` and `POST /api/v1/auth/refresh` issue HS256 tokens (30-minute access, 7-day refresh). `GET /api/v1/auth/me` returns the current user. Supersedes the frontend auth stub.
● `User` model with role enum (analyst / operator / admin), bcrypt password hashing, alembic migration `0002_create_user`.
● `get_current_user` dependency wired onto every `/elsets` route. `POST /elsets/ingest` now records the authenticated user's `id` and IP address in the audit log.
● Admin bootstrap script at `backend/scripts/create_admin.py`. Run via `python -m scripts.create_admin --username <name> --password <secret>` from the `backend/` directory.
● Frontend axios refresh-on-401 interceptor; `AuthContext` now talks to the real backend.
● Backend tests for password hashing, JWT round-trip, login flow (happy path, wrong password, unknown user, inactive user), `/auth/me` token validation, refresh, and the auth gate on `/elsets/ingest`.
● Decision log ADR-010 (JWT authentication with stateless refresh, supersedes ADR-009).
● End-to-end UDL element-set ingest. `Elset` model, alembic baseline migration, async UDLClient, ingest service with `(udl_id)` upsert, hash-chained audit writes, REST API at `/api/v1/elsets`.
● Analyst-facing Element sets page with filter, pagination, and a manual ingest trigger. Styled against the Bluestaq palette.
● Frontend scaffold: `index.html`, `main.tsx`, `ProtectedRoute`, `Layout`, `Login`, `Dashboard`, axios client, design tokens.
● Audit writer with SHA-256 hash chain and Postgres advisory-lock concurrency control.
● Alembic configuration (`alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`).
● Backend tests covering the UDL client (happy path, 401, 500, non-list responses, missing credentials, epoch formatting) and the UDL-to-model field mapping.
● Documentation set: README, architecture overview, data model, security overview, audit overview, developer setup, operator manual, analyst training manual, Phase 1 roadmap, this changelog.
● Decision log entries ADR-007 (UDL ingest pattern), ADR-008 (hash-chained audit), ADR-009 (frontend auth stubbed, now superseded).

### Changed

● `POST /auth/refresh` response is now `TokenResponse` (both `access_token` and `refresh_token`) instead of `RefreshResponse`. Frontend stores the new refresh token returned by the server.
● `POST /auth/logout` now takes a body `{refresh_token: "..."}` instead of relying on the access-token header. Supersedes the bearer-only logout from the prior auth-events slice.
● **Documentation aligned to the Bluestaq Ltd Document Design and Narrative Style Guide v3 (March 2026).** Every doc now carries the brand-banner top line, the metadata block, `**SECTION NN**` eyebrows before every H2 (or `**ADR-NNN**` in the decision log), copper and blue callout patterns where they earn their place, and the standard footer line. Version bumped to 0.2 across the set.
● `Settings` now exposes `UDL_USERNAME`, `UDL_PASSWORD`, `UDL_REQUEST_TIMEOUT_SECONDS`, and `UDL_VERIFY_SSL`.
● `.env.example` mirrors the new UDL configuration.

### Removed

● Frontend stub authentication (any-non-empty-username accepted). Superseded by real backend JWT.

### Fixed

● Frontend `context/AuthContent.tsx` typo replaced with the correctly-named `AuthContext.tsx`.

### Security

● Bcrypt password hashing via `passlib`. JWT signed with `APP_SECRET_KEY` using HS256. Tokens travel in the `Authorization` header, never in cookies.
● No real credentials are stored in source. `.env*` is gitignored; `.env.example` is the only committed environment file.
● gitleaks runs in CI and as a pre-commit hook.
● bandit at severity `-ll` runs across `backend/app/` in CI and pre-commit.

## Prior history

Captured in git log up to `18fff46` (Merge pull request #1, CI pipeline check).

Bluestaq Limited | Daily Operations Dashboard documentation | 2026
