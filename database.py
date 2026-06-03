from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import sqlite3
from typing import Iterator


DATABASE = "SQLitePython.db"


USER_COLUMNS = (
    "id",
    "discord_id",
    "avatar",
    "discriminator",
    "username",
    "level",
    "xp_level",
    "xp_cap",
    "total_xp",
    "message_count",
)


@dataclass
class UserRecord:
    id: int
    discord_id: str
    avatar: str | None
    discriminator: str | None
    username: str | None
    level: int
    xp_level: int
    xp_cap: int
    total_xp: int
    message_count: int


@contextmanager
def connect(db_file: str = DATABASE, *, readonly: bool = False) -> Iterator[sqlite3.Connection]:
    if readonly:
        connection = sqlite3.connect(f"file:{db_file}?mode=ro", timeout=30.0, uri=True)
    else:
        connection = sqlite3.connect(db_file, timeout=30.0)
    connection.row_factory = sqlite3.Row
    if not readonly:
        connection.execute("PRAGMA journal_mode=WAL")
    try:
        yield connection
        if not readonly:
            connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    """Keep startup compatible with the existing database; do not create a new schema."""
    with connect() as db:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_discord_id ON Users(discord_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_users_total_xp ON Users(total_xp)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_users_total_xp_desc ON Users(total_xp DESC)")


def row_to_user(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        id=row["id"],
        discord_id=row["discord_id"],
        avatar=row["avatar"],
        discriminator=row["discriminator"],
        username=row["username"],
        level=row["level"],
        xp_level=row["xp_level"],
        xp_cap=row["xp_cap"],
        total_xp=row["total_xp"],
        message_count=row["message_count"],
    )


def get_user(discord_id: int | str, *, readonly: bool = False) -> UserRecord | None:
    with connect(readonly=readonly) as db:
        row = db.execute(
            f"SELECT {', '.join(USER_COLUMNS)} FROM Users WHERE discord_id = ? LIMIT 1",
            (str(discord_id),),
        ).fetchone()
    return row_to_user(row) if row else None


def create_user(discord_id: int | str, avatar: str | None, discriminator: str | None, username: str | None) -> None:
    with connect() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO Users(
                discord_id, avatar, discriminator, username,
                level, xp_level, xp_cap, total_xp, message_count
            )
            VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0)
            """,
            (str(discord_id), avatar, discriminator, username),
        )


def get_or_create_user(
    discord_id: int | str,
    avatar: str | None,
    discriminator: str | None,
    username: str | None,
) -> UserRecord:
    user = get_user(discord_id)
    if user is not None:
        return user

    create_user(discord_id, avatar, discriminator, username)
    user = get_user(discord_id)
    if user is None:
        raise RuntimeError(f"Could not create user row for discord_id={discord_id}")
    return user


def update_user(user: UserRecord) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE Users
            SET avatar = ?,
                discriminator = ?,
                username = ?,
                level = ?,
                xp_level = ?,
                xp_cap = ?,
                total_xp = ?,
                message_count = ?
            WHERE discord_id = ?
            """,
            (
                user.avatar,
                user.discriminator,
                user.username,
                user.level,
                user.xp_level,
                user.xp_cap,
                user.total_xp,
                user.message_count,
                user.discord_id,
            ),
        )


def top_users(limit: int = 3, *, readonly: bool = False) -> list[UserRecord]:
    with connect(readonly=readonly) as db:
        rows = db.execute(
            f"SELECT {', '.join(USER_COLUMNS)} FROM Users ORDER BY total_xp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_user(row) for row in rows]


def get_rank(user: UserRecord, *, readonly: bool = False) -> int:
    with connect(readonly=readonly) as db:
        row = db.execute(
            "SELECT COUNT(*) AS rank FROM Users WHERE total_xp >= ?",
            (user.total_xp,),
        ).fetchone()
    return int(row["rank"])
