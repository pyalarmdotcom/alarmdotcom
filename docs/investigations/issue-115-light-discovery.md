# Issue 115: light discovery investigation

Investigation prepared for `2026.10.30b1` on `release/2026.10.30b1`, originally developed on `fix/light-discovery-probe`. The probe is diagnostic only; no affected-account fix has been confirmed.

## Findings

HA-ADC/pyadc at `97e7fc274172a3aa8d8a0a23c99d9a48960709b6` does not solve the account-specific discovery gap by itself. Its `LightController` inherits `BaseController.fetch_all()`, which requests the unscoped `devices/lights` endpoint. It does not obtain light IDs from the system relationship before that request. The issue reporter has already established that their account rejects the unscoped endpoint and accepts `ids[]` requests.

Our current path gets no IDs from the catalog, requests the selected system detail, and receives a parsed `lights` relationship with zero entries. Presence of a relationship does not establish that its `data` array was populated. The reported relationship count of 33 counts relationship names, not lights.

The published example with `lights.data` parses correctly locally. Additional synthetic reproductions confirm that adding metadata, links, or both does not lose those IDs. A relationship containing only links and metadata is also valid JSON:API and yields no embedded IDs. That is a hypothesis to distinguish, not a confirmed explanation for this account.

## Changes prepared here

The existing fallback system-detail request can now emit a DEBUG-only, count-only probe. The probe records predefined structure labels, raw versus parsed entry and usable-ID counts, whether the ID sets match, whether the response includes the requested system, whether a related link exists, and a bounded numeric metadata count. The request also reports whether the requested system is among the already loaded systems.

IDs are compared in memory and are never included in the probe output. Names, URLs, response bodies, headers, credentials, arbitrary field names, metadata strings, and exception messages are excluded. The diagnostic flag is consumed internally and never forwarded to aiohttp. Probe failures do not interrupt discovery. No new endpoint is requested, no link is followed, and the existing discovery behavior is unchanged.

## Next live comparison

On the maintainer's working system, enable `_pyalarmdotcomajax: debug` temporarily and capture only `Light discovery:` and `Light discovery probe:` lines while reloading. The fallback probe runs only when ordinary discovery finds no lights, so a working account may not exercise it. The absence of that probe on a working account is not evidence that it is broken.

Possible outcomes on the affected account, once this investigation is ready for testing:

- Raw IDs exist but differ from parsed IDs: investigate the parser with a matching synthetic structure.
- Both counts are zero and a related link or positive metadata count is present: investigate lazy relationship expansion using the actual portal sequence.
- The requested system is missing from the loaded system collection or does not match the response: investigate account/system selection.
- Both counts match and contain IDs: continue through the scoped lights request and model registration.

The b1 release notes provide a specific affected-account test: reload once with library debug logging enabled, then share only the discovery/probe lines. Actual affected-account behavior remains unverified. This is a diagnostic test, not a promised fix.

## Maintainer browser captures and Homebridge comparison

The maintainer supplied browser responses directly. The system-detail example contains one light in `relationships.lights.data`, with `meta.count` represented as a numeric string. The root system ID is a JSON number, while its relationship references are strings. A neutral reproduction of this structure parses successfully and retains the light entry. The supplied identity response's selected system matches the pasted system-detail ID. These observations describe the working maintainer account and do not establish the behavior of the affected reporter account.

Corrected the unreleased probe to normalize numeric system IDs for equality checks and accept bounded decimal-string metadata counts. Without this, the probe could falsely report a system mismatch or miss the declared count even though the main parser handles the response correctly. All public fixtures use synthetic IDs and names; the user's account data and attachments are not added to this repository.

The Homebridge plugin delegates API access to `node-alarm-dot-com/node-alarm-dot-com` (reviewed at `403afb60560dac357d2a6b695664cd2181fee619`). That library obtains system IDs from `identities.data[].relationships.selectedSystem.data.id`, loads `systems/systems/{id}`, then reads `relationships.lights.data` and issues ID-scoped light requests. This differs from our available-system selection source and remains a comparison to investigate on the affected account, rather than a reason to change systems automatically. It batches queries into at most 50 device IDs. Its camera snapshot helper uses `video/snapshots/{cameraId}` to obtain a signed image URL, a separate avenue for future camera investigation. No panic activation or temporary user-access management implementation was found in the reviewed source.
