CREATE TABLE social_forum_posts (
    post_id UUID PRIMARY KEY,
    author_uid TEXT NOT NULL CHECK (length(author_uid) BETWEEN 1 AND 128),
    title VARCHAR(120) NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
    body VARCHAR(5000) NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 5000),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    moderated_at TIMESTAMPTZ,
    moderator_uid TEXT CHECK (moderator_uid IS NULL OR length(moderator_uid) BETWEEN 1 AND 128),
    CHECK ((status = 'pending' AND moderated_at IS NULL AND moderator_uid IS NULL)
        OR (status <> 'pending' AND moderated_at IS NOT NULL AND moderator_uid IS NOT NULL))
);

CREATE INDEX social_forum_approved_created_idx
    ON social_forum_posts (created_at DESC, post_id DESC) WHERE status = 'approved';
CREATE INDEX social_forum_pending_created_idx
    ON social_forum_posts (created_at ASC, post_id ASC) WHERE status = 'pending';
