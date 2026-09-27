# CLAUDE.md

Python SDK for the seventhings Customer API. It is a port of the Go SDK (`../customer-api-go`, the reference implementation) and keeps parity with it and with the PHP SDK (`../customer-api-php`). When the SDKs disagree, Go wins.

## Commands

```sh
uv run pytest                          # unit tests (integration tests are deselected by default)
uv run ruff check . && uv run ruff format --check .
uv run mypy                            # strict; covers src, tests, examples, scripts
uv run python scripts/unasync.py       # regenerate the sync client (use --check in CI)
scripts/run-integration.sh [pytest args]   # live tests; needs .env (see .env.example)
```

## Layout

- `src/seventhings/_operations.py`: one builder per endpoint. Each returns an `Operation` (method, path, query, body, accept, auth flag, response parser) and does no I/O. Request shapes and decoding live **only** here.
- `src/seventhings/_async/client.py`: `AsyncClient` plus the `Async*Service` classes that run those operations. This is the **source** file.
- `src/seventhings/_sync/client.py`: **generated** by `scripts/unasync.py`. Never edit it by hand.
- `src/seventhings/_transport.py`: `Operation`, `Response`, URL, header and error handling.
- `src/seventhings/models/`: frozen dataclasses with lenient `from_dict`/`to_dict`, `str` enums, `ListOptions` query encoders, and `Fields`.
- `tests/unit/`: the `h` fixture (`conftest.py`) runs every test against both the sync and the async client using `httpx.MockTransport`. `test_parity.py` maps every Go method to its Python counterpart and checks that sync and async signatures match.

## Adding an endpoint

1. Add a builder to `_operations.py`.
2. Add the method to the matching service in `_async/client.py`.
3. Run `scripts/unasync.py`.
4. Add unit tests using the `h` fixture, and add the Go method to `GO_PARITY`.

## API quirks the code relies on (don't "fix" them)

**Created IDs**
- New resources return their UUID in the `Location` header.
- Files use `Location-UUID`; hub orders return an integer in `Location-Id`.

**Response shapes**
- Lists come back as `{items}` for objects, rooms, locations, files, rentals and the hub.
- Tasks, field definitions and report templates come back as bare arrays.
- Users, persons and history use full page envelopes.

**Rooms and locations**
- They may answer with a `{uuid, fields}` envelope; `unwrap_resource_fields` flattens it.
- Their `patch` returns the record, or `None` if the body is empty. Every other `patch` returns `None`.

**Persons**
- `create` wraps the body in `{"fields": ...}`, but `patch` does not.
- The UUID comes from `person_uuid` and falls back to `uuid`.

**Circularity Hub**
- `suggest_*` answers `[]` when there are no suggestions; the SDK returns `None`.

**Query strings**
- Brackets are sent literally; only values are escaped (`quote_plus`).
- `like`, `not_like`, `in` and `nin` use the `[]` array form.

**Headers**
- `Content-Type: application/json` is sent only when there is a body (archive and unarchive send none).
- Raw downloads and multipart uploads send no `Accept: application/json`; report creation sends `Accept: application/pdf`.
- Ping and `POST auth_token` never send `Authorization`.

**SSO login**
- Uses `grant_type=sso_auth_code` and `provider_name`. The PHP SDK's `sso`/`provider` is wrong.
