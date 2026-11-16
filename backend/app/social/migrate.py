"""Apply versioned social PostgreSQL migrations."""

import os

from app.social.database import migrate_social_database


def main() -> None:
    database_url = os.environ.get("SOCIAL_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("SOCIAL_DATABASE_URL is required")
    migrate_social_database(database_url)


if __name__ == "__main__":
    main()
