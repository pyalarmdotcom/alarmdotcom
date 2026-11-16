# Temporary access for existing users, issue #108

`alarmdotcom.set_temporary_access` is prepared for beta `2026.10.30b1`.
The portal's read and write formats were captured on October 30, 2026. The
implementation has automated tests with synthetic resources. No automated test
contacts Alarm.com, and the integration action has not been tested on a live account.

## Supported operation

Set or change a temporary start/end interval for an existing user whose current
weekly schedule is null and whose access-plan relationship is empty. The action
keeps the existing PIN, role, pause status, and unknown attributes. It does not
create/delete users, change PINs, replace weekly restrictions, or clear a temporary
schedule to grant unrestricted access. Those operations require separate captures.

```yaml
action: alarmdotcom.set_temporary_access
data:
  config_entry_id: your_alarmdotcom_config_entry_id
  system_id: "900002"
  user_id: "900001"
  begin: "2027-01-05T12:00:00-05:00"
  end: "2027-01-10T12:00:00-05:00"
```

The IDs and dates above are synthetic. Select the account in the action editor.
Use its Alarm.com system ID and the existing user's ID from the portal user page
URL. Start/end accept ISO 8601 strings with `Z` or an explicit UTC offset. Naive
timestamps and non-increasing intervals are rejected. Each endpoint is converted
independently to UTC, so use the correct offset for that date when crossing DST.

## Captured API behavior

- GET and PUT use `/web/api/users/access/deviceAccesses/{user_id}`.
- Both include the selected system's `context-id` header and the existing session's
  anti-forgery header, supplied through the shared bridge request transport.
- GET returns a JSON:API resource of type `users/access/device-access`.
- PUT sends a flat object of type `users/access/device-accesses`, without a `data`
  or `attributes` wrapper. Related user and summary types are also pluralized.
- PUT contains the fresh GET attributes and flattened relationship identifiers.
  `temporarySchedule` contains `beginDateTime` and `endDateTime` in UTC.
- The observed successful PUT returned HTTP 200 and a single access resource.
  `credentialStatusDesc` may still report device synchronization in progress.

## Preservation and failure behavior

The manager serializes updates within each bridge and fetches current access just
before each write. It verifies resource and relationship identities, requires the
captured relationship shape, and refuses weekly schedules and nonempty access
plans. Unknown attributes are preserved rather than silently discarded.

Access documents and PINs remain local to the request. They are not cached in
resource controllers, entities, diagnostics, or configuration. The action never
accepts a PIN. Its generic transport/parser error omits exception text so server
content cannot enter the automation trace. Request logs contain method/type/status
only. All repository examples and tests use synthetic values.

The PUT disables automatic login-repair replay. After a transport failure or an
unconfirmed result, check the portal before invoking the action again. A read/write
race with another browser or client remains possible because no conditional-write
API has been verified. A matching saved schedule confirms server acceptance,
not credential synchronization at every panel and lock.

## Remaining live verification

1. Install the unreleased combined 2026.11.01b0 test build when ready to test.
2. Use a disposable existing test user with no weekly schedule or access plan.
3. Invoke the action once and confirm the saved interval in the portal.
4. Verify eventual provisioning and enforcement on the intended panel/lock.
5. Confirm another user's settings and the test user's PIN/role remain unchanged.

All-times/restricted transitions, read-only status entities, schedule clearing,
and user creation remain outside this implementation.

## Follow-up: confirming equivalent timestamps

A b1 hardware test returned the confirmation error after the PUT. The original
comparison required identical timestamp strings, so equivalent instants formatted
with different fractional seconds or UTC offsets could be rejected. This is a
confirmed validation weakness, not yet the confirmed cause of that live result.

The follow-up compares timezone-aware instants without rounding away differences.
A mismatched PUT representation triggers one GET of the requested user to verify
persisted dates. It never resends the credential PUT. A missing schedule, naive
server timestamp, wrong identity, or different instant remains unconfirmed.


## Read-only response action

`alarmdotcom.get_temporary_user_schedule` is a standard HA response-only action, usable by scripts and an existing MCP connection that supports actions with response data. It resolves the selected loaded account and verifies system membership before reading. The API manager performs one GET under its access lock and validates the returned user identity. It never performs a credential write.

The returned allowlist is `temporary_schedule` (UTC `begin`/`end`, or null) and `credential_status` (the server's integer value, or null). No arbitrary server descriptions, PINs, raw documents, or unknown attributes are returned. Unknown status values are not interpreted. A null schedule does not assert unrestricted access. Validation/errors remain credential-free. Last-entry unload removes the read service alongside the write service.
