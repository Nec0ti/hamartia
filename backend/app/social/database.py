"""PostgreSQL migrations and owner-scoped social profile storage."""

from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_LOCK_ID = 742193881
PROFILE_COLUMNS = (
    "nickname", "age", "school_grade", "school_class", "curriculum",
    "study_preferences", "study_goals", "avatar_preset", "nickname_public",
    "age_public", "school_grade_public", "school_class_public", "curriculum_public",
    "study_preferences_public", "study_goals_public", "avatar_preset_public",
)


def migrate_social_database(database_url: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
        connection.execute(
            "CREATE TABLE IF NOT EXISTS social_schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        for migration in sorted(MIGRATIONS_DIR.glob("[0-9]*_*.sql")):
            version = migration.name.split("_", 1)[0]
            applied = connection.execute(
                "SELECT 1 FROM social_schema_migrations WHERE version = %s", (version,)
            ).fetchone()
            if applied:
                continue
            connection.execute(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO social_schema_migrations (version) VALUES (%s)", (version,)
            )


class PostgresProfileRepository:
    def __init__(self, database_url: str, *, max_connections: int = 10):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=max_connections,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        self.max_connections = max_connections

    def open(self) -> None:
        self.pool.open()
        self.pool.wait(timeout=10)

    def close(self) -> None:
        self.pool.close()

    def get_profile(self, uid: str) -> dict | None:
        columns = ", ".join(PROFILE_COLUMNS)
        with self.pool.connection() as connection:
            return connection.execute(
                f"SELECT {columns} FROM social_profiles WHERE uid = %s", (uid,)
            ).fetchone()

    def patch_profile(self, uid: str, changes: dict) -> dict:
        columns = tuple(name for name in changes if name in PROFILE_COLUMNS)
        if len(columns) != len(changes):
            raise ValueError("Unknown profile field")
        if not columns:
            return self.get_profile(uid) or {}

        insert_columns = ("uid", *columns)
        names_sql = ", ".join(insert_columns)
        values_sql = ", ".join("%s" for _ in insert_columns)
        updates_sql = ", ".join(f"{name} = EXCLUDED.{name}" for name in columns)
        return_columns_sql = ", ".join(PROFILE_COLUMNS)
        values = (uid, *(changes[name] for name in columns))
        with self.pool.connection() as connection:
            return connection.execute(
                f"INSERT INTO social_profiles ({names_sql}) VALUES ({values_sql}) "
                f"ON CONFLICT (uid) DO UPDATE SET {updates_sql}, updated_at = now() "
                f"RETURNING {return_columns_sql}",
                values,
            ).fetchone()

    def stats(self) -> dict:
        return self.pool.get_stats()
