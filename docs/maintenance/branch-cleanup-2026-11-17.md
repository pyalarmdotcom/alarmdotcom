# Branch cleanup, November 17, 2026

Thirteen obsolete branches were removed after checking live branch heads, merged pull requests, and patch equivalence. No pull requests were merged or closed during this cleanup. No default branch, tag, published release, or runtime behavior was changed.

## Original repository

Compared against master `3d8b4b86bf71ef7e290d8c35aaeec52e683901c3`.

| Removed branch | Last commit | Disposition |
| --- | --- | --- |
| release/2026.11.17 | b3da4a957527a965785a07f91f9b6e8293934ac2 | Merged in [PR #568](https://github.com/pyalarmdotcom/alarmdotcom/pull/568); ancestor of master. |
| beta/2026-modernization | 7c34a5275661bb9bd79111f697aad85fd91027d4 | All commits are ancestors of master; stable modernization supersedes this staging branch. |
| dependabot/pip/colorlog-6.10.1 | c5248c57e51d5fe37ecf0259ea4951c34eb7d280 | [PR #497](https://github.com/pyalarmdotcom/alarmdotcom/pull/497) was closed as superseded; current development requirements use colorlog 6.12.0. |
| dependabot/pip/homeassistant-2023.6.2 | fef39207594210a7cb5873c5055300e7bd09664b | Old closed [PR #306](https://github.com/pyalarmdotcom/alarmdotcom/pull/306); obsolete 2023 development pin, superseded by the current toolchain and HA 2026.11 compatibility matrix. |

Retained `master`, `docs/webrtc-card-attribution`, and `v3-master`. The legacy v3 branch has distinct historical source and was not treated as merged.

## Maintained distribution

Compared against main `40756e3fa39f2d28fbb703d7c11c1c3b409737ed`. For squash merges, `git cherry origin/main <branch>` showed the branch patch already present, even when the original commit itself was not an ancestor.

| Removed branch | Last commit | Merged PR | Verification |
| --- | --- | --- | --- |
| fix/stable-camera-trouble-conditions | ffaeeb580792914c8cb35a5e0251ee14bf45a705 | [#174](https://github.com/ibasebcast/ha-alarmdotcom/pull/174) | Ancestor |
| fix/camera-kiosk-and-valve-discovery | b471408045e9db1e2315a6908312aeb750770a17 | [#182](https://github.com/ibasebcast/ha-alarmdotcom/pull/182) | Ancestor |
| fix/setup-guidance-2026-11-10 | a7ccf52fb5be75f2bd58891fc631acf7e7fceefb | [#186](https://github.com/ibasebcast/ha-alarmdotcom/pull/186) | Ancestor |
| fix/stable-2026-11-12 | 7fd90ca19c71039f253600e16f33b10964968189 | [#187](https://github.com/ibasebcast/ha-alarmdotcom/pull/187) | Equivalent patch |
| fix/websocket-shutdown-176 | 9e5bac0e5dd285dc47ae34f2875cbd11b14a19c0 | [#191](https://github.com/ibasebcast/ha-alarmdotcom/pull/191) | Equivalent patch |
| fix/water-valve-initial-refresh-189 | afda6e233efd32f3f0fd6c6067e15bb6fc07a4c8 | [#192](https://github.com/ibasebcast/ha-alarmdotcom/pull/192) | Equivalent patch |
| docs/troubleshoot-gray-camera-190 | 5c6245680dae8844688be7790e4e4d84d4db002a | [#193](https://github.com/ibasebcast/ha-alarmdotcom/pull/193) | Equivalent patch |
| release/2026.11.14 | f7ab803dbe7d41de5c12a87feea3047f2878469b | [#194](https://github.com/ibasebcast/ha-alarmdotcom/pull/194) | Equivalent patch |
| release/2026.11.15-camera-diagnostics | f94bfa948a167d32330fbba9213b2bb871e23604 | [#198](https://github.com/ibasebcast/ha-alarmdotcom/pull/198) | Equivalent patch |

Retained main and active branches:
- `beta/issue-157-sign-in`: draft [PR #169](https://github.com/ibasebcast/ha-alarmdotcom/pull/169), ongoing sign-in/arming investigation; not part of stable.
- `dependabot/pip/homeassistant-2026.11.1`: [PR #188](https://github.com/ibasebcast/ha-alarmdotcom/pull/188), outstanding checks need review.
- `dependabot/pip/pytest-asyncio-gte-1.5.0`: [PR #196](https://github.com/ibasebcast/ha-alarmdotcom/pull/196), outstanding checks need review.
- `dependabot/pip/ruff-gte-0.17.5`: [PR #197](https://github.com/ibasebcast/ha-alarmdotcom/pull/197), pending dependency review.
- `docs/webrtc-card-attribution`: corresponding credit and migration documentation changes prepared for review.

The original repository's glass-break device-class [PR #551](https://github.com/pyalarmdotcom/alarmdotcom/pull/551) also remains open. It is a separate improvement, not a superseded branch.

Removing a merged implementation branch does not establish that every reported hardware issue is resolved. Sign-in, camera streaming/recovery, and valve-state investigations remain open where further evidence is needed.
