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
```

If you have already set up `.env` for the integration tests, you can load it instead:

```sh
set -a && source .env && set +a && uv run python examples/demo/demo.py
```

The demo uses the synchronous `Client`. The same calls work on `AsyncClient` with `await`, or with `async for` for the `all()` iterators.

## What it does

The demo runs the steps below in order. Every object, task and person it creates is deleted again before it exits. The uploaded demo file stays on the instance, because the API has no endpoint for deleting files.

### 1. Auth

Logs in with the provided credentials and prints the user ID and a truncated access token.

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
- Creates a task with a deadline, assignee, reference and reminder
- Closes the task, reads its history, deletes it and confirms the 404
- Deletes the reference object

### 7. Persons

- Counts all persons and lists the first page (max 5)
- Looks up the first person by UUID and by numeric ID
- Lists the instance's mandatory person fields
- Creates a person, patches its department and reads its history
- Deletes the person and confirms the 404

### 8. History of existing resources

Reads the history of the first room, the first location and the first rental case, if the instance has any. When the rentals module is not active on the instance, the rentals step is skipped.

### 9. Auth cleanup

Revokes all tokens for the session.

## Expected output

```
── Auth ──────────────────────────────────────────
[Auth   ] Logging in…
[Auth   ] Logged in — user_id=3, token=eyJ0eXAiOiJKV1QiLCJh…

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
