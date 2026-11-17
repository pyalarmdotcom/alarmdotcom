# Snapshot and OTP resend follow-up

## Sources and scope

The earlier Homebridge comparison identified `video/snapshots/{cameraId}`. The Node API implementation at commit `403afb60560dac357d2a6b695664cd2181fee619`, `src/cameras.ts`, reads `data.attributes.url` and treats `attributes.error` as failure. The URL is signed and belongs to a separate video host. Parent integration issue 553 also identifies the snapshot endpoint. These are source-code/API leads, not a claim of live validation on every camera model.

Parent integration issue 538 reports SMS codes not arriving until requested again. Our existing setup requests the first SMS/email code, but did not provide an explicit resend control.

## Implementation

Snapshot metadata uses the existing authenticated camera API session. A separate short-lived, cookie-free client downloads the signed HTTPS image without Alarm.com credentials or AJAX headers. Redirects and URLs with embedded credentials are rejected. Downloads must be images, finish within 15 seconds, and remain within 10 MiB. Signed URLs are not exposed as HA attributes or logged in exception messages. Unsupported/malformed metadata and failed image downloads return no snapshot.

The OTP form offers an explicit resend checkbox for SMS/email. Selecting it and submitting requests another code without submitting any entered code. The form then accepts the new code normally. Delivery failures remain in the same flow with an error. Authenticator apps do not offer resend. No automatic resend loop is introduced. English strings and translations are updated together.

This branch is based on the camera reconnect fix, so both camera changes can be tested together. It does not merge speculative light-context changes, change system selection, implement recording/casting, or publish a beta. The image-sensor photo-association gap remains separate from video-camera snapshots.

## Live checks still required

- On a supported online camera, use HA's normal snapshot functionality and verify an actual image is returned. Confirm a camera that cannot supply snapshots fails gracefully.
- Repeat dashboard navigation and simultaneous viewing checks from issue 156.
- During a deliberately initiated SMS/email setup or reauthentication, request another code and finish with the delivered code. Do not reset an existing working login solely for this check.
- Confirm authenticator-app setup remains unchanged.

Automated coverage includes URL metadata, isolated image downloads, malformed/non-image/oversized results, missing URLs, secret-safe failure logs, SMS/email resend, resend failure, and authenticator behavior.
