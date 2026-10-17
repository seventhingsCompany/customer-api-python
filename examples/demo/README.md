# Demo

An end-to-end example that runs the core seventhings Python SDK modules against a live instance. It checks that the SDK works and shows new users how each API area is used.

## Prerequisites

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- A running seventhings instance with valid credentials and the REST API Integration active

## Usage

Set the required environment variables and run the demo from the repository root:

```sh
export SEVENTHINGS_BASE_URL=https://example.seventhings.com
export SEVENTHINGS_USERNAME=user@example.com
export SEVENTHINGS_PASSWORD=secret
export SEVENTHINGS_CLIENT_ID=your-client-id

uv run python examples/demo/demo.py
uv run python examples/demo/demo.py --rate-limit 400   # override the 200 requests/minute default (0 disables)
```

To log in with an OAuth authorization code + PKCE instead of a password, also set `SEVENTHINGS_AUTH_CODE`, `SEVENTHINGS_CODE_VERIFIER` and `SEVENTHINGS_REDIRECT_URI` (the username and password are then not needed). Codes are single-use, so get a fresh one from your authorization flow for each run.

If you have already set up `.env` for the integration tests, you can load it instead:

```sh
set -a && source .env && set +a && uv run python examples/demo/demo.py
```

The demo uses the synchronous `Client`. The same calls work on `AsyncClient` with `await`, or with `async for` for the `all()` iterators.

## What it does

The demo runs the steps below in order. Every object, task, person, catalog item and rental it creates is deleted again, also when a later step fails. The uploaded demo files stay on the instance, because the API has no endpoint for deleting files. If the API answers HTTP 429, the demo prints the `Retry-After` delay and stops; it never retries on its own.

### 1. Auth

Logs in with the provided credentials (or the PKCE code), prints the user ID and the active rate limit.

### 2. Objects: CRUD, barcode lookup and history

- Lists the first page of objects (max 5)
- Checks the new object's payload against the instance's mandatory asset fields (`field_definitions.missing_mandatory_fields`)
- Creates an object, finds it again by barcode, then patches its name
- Archives and unarchives the object
- Reads the object's change history (and a second page, if there is one)

### 3. Reports

- Lists the PDF report templates
- Renders the first template for the demo object and prints the size of the PDF

The demo object is then deleted, and the demo confirms the 404 that follows.

### 4. Objects: sorting, filtering and iteration

- Fetches the **5 most recently changed** assets by sorting on `updated_at DESC`
- Filters assets whose `inventory_name` contains "SDK", using the `like` operator
- Walks through all assets with `objects.all()`, stopping after 10

These calls show how to use `ListOptions` with `sort_by`, `where` and the pagination iterator.

### 5. Files

- Uploads a small text file
- Reads back its metadata (name, type, size)
- Creates a temporary object, attaches the file, then detaches it
- Deletes the temporary object

### 6. Tasks

- Looks up the current user's UUID
- Creates a temporary object to use as a task reference
- Creates a task with a deadline, assignee and reference, without reminders and with `notify=False`
- Updates it with a zero-interval reminder (on the deadline), then with `reminders=[]` (disabled), checking each
- Closes the task, reads its history, deletes it and confirms the 404
- Deletes the reference object

### 7. Persons

- Counts all persons and lists the first page (max 5)
- Looks up the first person by UUID and by numeric ID
- Lists the instance's mandatory person fields
- Creates a person, patches its department and reads its history
- Deletes the person and confirms the 404

### 8. Product catalog

Creates a temporary catalog item, reads it, replaces its fields with a PUT, finds it with a filtered list, deletes it and confirms the 404. Skipped when the catalog feature or the create right is missing.

### 9. Timed rental

Creates a temporary object and a timed rental (`is_full_day=False`, `issue_at`/`due_at` with a +02:00 offset), checks the stored times, extends the return time, converts the rental to a full-day rental and then deletes both.

### 10. Custom thumbnail

Uploads a 640x480 PNG, downloads a 320x240 thumbnail, checks its dimensions and that a second request returns the cached image.

### 11. History of existing resources

Reads the history of the first room, the first location and the first rental case, if the instance has any. When the rentals module is not active on the instance, the rentals step is skipped.

### 12. Auth cleanup

Revokes all tokens for the session.

## Expected output

```
── Auth ──────────────────────────────────────────
[Auth   ] Logging in…
[Auth   ] Logged in — user_id=3
[Rate   ] Limit: 200 requests/minute, evenly spaced; shared by all calls

── Objects ──────────────────────────────────────────
[Objects] Listing objects…
[Objects] Listed 5 object(s) (first page, max 5)
[Objects] Payload satisfies all mandatory asset fields
[Objects] Created object <uuid>
[Objects] Found by barcode SDK-DEMO-<timestamp> — inventory_name=SDK Demo Object
[Objects] Patched object — inventory_name=SDK Demo Object (updated)
[Objects] Archived object <uuid>
[Objects] Unarchived object <uuid>
[History] Objects — 4 entries, page=1 per_page=5 total=4
[History] Object event: type=asset date=2026-09-27T21:18:32+00:00
...

── Reports ──────────────────────────────────────────
[Reports] Listing PDF templates…
[Reports] Found 1 template(s)
[Reports] Rendered template 'Übergabeprotokoll' — 421273 PDF bytes
[Objects] Deleted object <uuid>
[Objects] Confirmed deletion (404)

── Objects ──────────────────────────────────────────
[Objects] Fetching last 5 changed assets (sorted + filtered)…
[Objects] Got 5 recently changed asset(s):
[Objects]   1. Some Asset (updated_at=2026-09-23 20:26:41)
[Objects]   ...

── Objects ──────────────────────────────────────────
[Objects] Filtering assets by name containing "SDK"…
[Objects] Got 0 asset(s) matching filter:

── Objects ──────────────────────────────────────────
[Objects] Iterating all assets via objects.all() (capped at 10)…
[Objects]   • Tisch Meetingraum (<uuid>)
[Objects]   ...
[Objects] Iterated 10 asset(s) before stopping

── Files ──────────────────────────────────────────
[Files  ] Uploading file…
[Files  ] Uploaded file <uuid> (demo.txt, 44 bytes)
[Files  ] File metadata — name=demo.txt, type=text/plain, size=44
...

── Tasks ──────────────────────────────────────────
[Tasks  ] Creating task…
...
[Tasks  ] Verified reminders: [TimeInterval(unit=<TimeIntervalUnit.DAYS: 'days'>, value=0)] (empty disables reminders)
[Tasks  ] Verified reminders: [] (empty disables reminders)
[History] Tasks — 2 entries, page=1 per_page=5 total=2
[Tasks  ] Deleted task <uuid>
[Tasks  ] Confirmed deletion (404)

── Persons ──────────────────────────────────────────
[Persons] Counting and listing persons…
[Persons] persons.count() → 6 person(s)
[Persons] Got 5 person(s) (page 1, max 5):
[Persons]   1. id=1 uuid=<uuid> Alice Smith <alice@example.com>
...
[Persons] Instance-required person field(s): ['email']
[Persons] Created person <uuid> <sdk.demo+…@example.com>
[Persons] Patched person <uuid> (department=IT)
[History] Persons — 2 entries, page=1 per_page=5 total=2
...
[Persons] Deleted person <uuid>
[Persons] Confirmed deletion (404)

── Catalog ──────────────────────────────────────────
[Catalog] Creating a temporary catalog item…
[Catalog] Verified create, get, PUT and filtered list — total=1
[Catalog] Confirmed deletion (404)

── Rentals ──────────────────────────────────────────
[Rentals] Creating and updating a timed rental…
[Rentals] Verified timed rental <issue_at> → <due_at> (exclusive)
[Rentals] Verified extended return time and conversion to full-day
[Rentals] Cleaned up rental and object

── Files ──────────────────────────────────────────
[Files  ] Uploading an image and verifying a custom thumbnail…
[Files  ] Uploaded image <uuid>; it remains because the API has no delete endpoint
[Files  ] Verified 320x240 thumbnail and cached response (… bytes)

── History ──────────────────────────────────────────
[History] Reading history for existing resources…
[History] Rooms — 1 entries, page=1 per_page=5 total=1
[History] Locations — 1 entries, page=1 per_page=5 total=1
[History] Rentals — 1 entries, page=1 per_page=5 total=1

── Auth ──────────────────────────────────────────
[Auth   ] Revoking tokens…
[Auth   ] Tokens revoked

Done — all steps completed successfully.
```
