# Issue 156: camera reconnect after dashboard navigation

## Report and reproduced code behavior

The reporter sees a legacy signaling `Invalid token!` response after leaving and returning to a camera dashboard on stable 2026.10.28 and beta 2026.10.30b1. Another camera reconnects successfully. The maintainer reports similar dashboard-return symptoms on their cameras. Neither observation establishes a model-specific fault or a common underlying server cause.

Synthetic tests reproduce these gaps in the released card/backend:

- The legacy signaling handler ignores JSON error responses.
- A newly requested configuration identical to the previous configuration does not restart a disconnected stream.
- State updates on a detached card can start credential requests.
- State updates can bypass the automatic retry budget.
- The backend returns its cached credentials on browser requests unless the cache is empty.
- Concurrent refresh callers previously returned immediately rather than waiting for the current fetch.

## Change

New browser credential requests fetch current stream information from Alarm.com. Concurrent requests for the same camera wait for the in-flight result. The result is published before releasing the fetch lock. A failed fetch clears the previous credentials. Existing camera authorization checks remain in place, and credentials stay out of entity state.

Legacy signaling errors trigger bounded session recovery using a fixed, non-sensitive reason. Recovery discards the old credentials and transports before requesting credentials again. Both legacy and Janus retries follow the same cleanup path. An unchanged response can still start a disconnected stream. Detached cards do not initiate requests; genuine dashboard returns get a fresh retry budget. The one-second rotation/reparenting grace period remains.

The change introduces extra Alarm.com stream-info requests when a new browser session starts. It does not establish whether tokens are single-use or how each camera model expires tokens. Multiple viewers and multiple cameras need live verification.

## Live validation still required

Use the separate fix branch for testing; the published beta is unchanged. Restart HA after installing the backend changes and fully reload the browser so it loads the updated card (the registered static resource is cached). Do not publish a new release or overwrite an existing beta as part of this branch.

1. Confirm both legacy and Janus cameras still establish streams where available.
2. Leave the dashboard for several seconds, return, and repeat at least ten times. Confirm moving timestamps without integration reloads.
3. Repeat a quick dashboard switch and phone rotation. Confirm the retained active stream still works.
4. View two cameras together and, if available, the same camera in two browser tabs. Check that reconnecting one does not interrupt the other.
5. If a token rejection occurs, confirm automatic recovery or a bounded Reconnect button, rather than an indefinite session-refresh placeholder.
6. Check that unauthorized HA users cannot request camera credentials and no credentials appear in HA attributes or logs.

Automated tests cover these client lifecycle/error paths, backend refresh freshness/concurrency/failure, and the existing permission gate. They do not replace live camera testing.
