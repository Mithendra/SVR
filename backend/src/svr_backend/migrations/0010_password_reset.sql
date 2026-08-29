-- 0010_password_reset.sql - single-use, time-limited password-reset tokens
-- (SDD 13.1). Both the self-service "Forgot Password" flow and the admin-initiated
-- reset from Manage Users issue one of these and email the link; the password
-- value itself is never stored, displayed, or transmitted.

CREATE TABLE password_reset_token (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_by  TEXT,                 -- login_name of the admin, or NULL for self-service
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_reset_token_user ON password_reset_token (user_id);
