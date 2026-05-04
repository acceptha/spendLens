import asyncpg

from app.settings import settings


async def ensure_admin_user(conn: asyncpg.Connection) -> None:
    """Insert admin user from ENV if not exists. Idempotent."""
    await conn.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES ($1, $2)
        ON CONFLICT (email) DO NOTHING
        """,
        settings.admin_email,
        settings.admin_password_hash,
    )
