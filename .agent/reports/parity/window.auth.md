# window.auth

PARITY-GAP window.auth: guest login is not on the sidecar. The Qt login window can open a volatile session with `VaultManager.create_guest_vault` and no password. `auth.unlock` only opens an existing account vault in the sidecar process. The React shell has no guest path.

Create-account is not a gap: it keeps `create_user_account` / `session.create_account`, then calls `auth.unlock` so the sidecar holds the C++ session.
