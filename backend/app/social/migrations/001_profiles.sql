CREATE TABLE social_profiles (
    uid TEXT PRIMARY KEY CHECK (length(uid) BETWEEN 1 AND 128),
    nickname VARCHAR(80),
    age INTEGER CHECK (age IS NULL OR age BETWEEN 5 AND 120),
    school_grade VARCHAR(80),
    school_class VARCHAR(80),
    curriculum VARCHAR(120),
    study_preferences VARCHAR(2000),
    study_goals VARCHAR(2000),
    avatar_preset VARCHAR(24) CHECK (
        avatar_preset IS NULL OR avatar_preset IN (
            'sunrise', 'moon', 'leaf', 'star', 'book', 'mountain', 'wave', 'lantern'
        )
    ),
    nickname_public BOOLEAN NOT NULL DEFAULT FALSE,
    age_public BOOLEAN NOT NULL DEFAULT FALSE,
    school_grade_public BOOLEAN NOT NULL DEFAULT FALSE,
    school_class_public BOOLEAN NOT NULL DEFAULT FALSE,
    curriculum_public BOOLEAN NOT NULL DEFAULT FALSE,
    study_preferences_public BOOLEAN NOT NULL DEFAULT FALSE,
    study_goals_public BOOLEAN NOT NULL DEFAULT FALSE,
    avatar_preset_public BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
