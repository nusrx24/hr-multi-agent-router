"""
Database module for the HR Multi-Agent Router.

Manages SQLite connections and provides CRUD operations for
the audit_log (append-only) and memory (STM/LTM) tables.
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional

from config import get_settings
from models import AuditLogEntry, MemoryEntry, MemoryType

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Database Path ──────────────────────────────────────────────

DB_PATH = settings.database_url


# ── Schema Initialization ─────────────────────────────────────


async def init_db() -> None:
    """
    Initialize the SQLite database and create tables if they don't exist.

    Tables:
        - audit_log: Append-only log of all requests and routing decisions.
        - memory: Two-tier memory system (STM for recent turns, LTM for facts).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # ── Audit Log Table (APPEND-ONLY) ──
        # No UPDATE or DELETE operations are ever exposed for this table.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
                user_id     TEXT    NOT NULL,
                request_text TEXT   NOT NULL,
                intent      TEXT    NOT NULL,
                confidence  REAL    NOT NULL,
                sub_agent   TEXT    NOT NULL,
                response    TEXT    NOT NULL,
                error       TEXT
            )
        """)

        # ── Memory Table (STM / LTM) ──
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             TEXT    NOT NULL,
                content             TEXT    NOT NULL,
                memory_type         TEXT    NOT NULL CHECK(memory_type IN ('stm', 'ltm')),
                significance_score  REAL    NOT NULL DEFAULT 0.0,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ── Indexes for fast lookups ──
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_user ON memory(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(user_id, memory_type)"
        )

        await db.commit()
        logger.info("Database initialized successfully at %s", DB_PATH)


# ── Audit Log CRUD (Append-Only) ──────────────────────────────


async def insert_audit_log(entry: AuditLogEntry) -> int:
    """
    Insert a new audit log entry. This is the ONLY write operation
    allowed on the audit_log table — enforcing append-only behavior.

    Args:
        entry: The audit log entry to insert.

    Returns:
        The ID of the newly inserted row.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO audit_log
                (timestamp, user_id, request_text, intent, confidence, sub_agent, response, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp.isoformat(),
                entry.user_id,
                entry.request_text,
                entry.intent,
                entry.confidence,
                entry.sub_agent,
                entry.response,
                entry.error,
            ),
        )
        await db.commit()
        logger.info("Audit log entry created: id=%s, intent=%s", cursor.lastrowid, entry.intent)
        return cursor.lastrowid


async def get_audit_logs(
    page: int = 1,
    limit: int = 20,
    user_id: Optional[str] = None,
) -> tuple[list[AuditLogEntry], int]:
    """
    Retrieve paginated audit log entries.

    Args:
        page: Page number (1-indexed).
        limit: Number of entries per page.
        user_id: Optional filter by user ID.

    Returns:
        A tuple of (list of entries, total count).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Build WHERE clause
        where_clause = ""
        params: list = []
        if user_id:
            where_clause = "WHERE user_id = ?"
            params.append(user_id)

        # Get total count
        count_row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM audit_log {where_clause}", params
        )
        total = count_row[0][0] if count_row else 0

        # Get paginated results (newest first)
        offset = (page - 1) * limit
        rows = await db.execute_fetchall(
            f"""
            SELECT * FROM audit_log {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )

        entries = [
            AuditLogEntry(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                user_id=row["user_id"],
                request_text=row["request_text"],
                intent=row["intent"],
                confidence=row["confidence"],
                sub_agent=row["sub_agent"],
                response=row["response"],
                error=row["error"],
            )
            for row in rows
        ]

        return entries, total


# ── Memory CRUD ────────────────────────────────────────────────


async def insert_memory(entry: MemoryEntry) -> int:
    """
    Insert a new memory entry (STM or LTM).

    Args:
        entry: The memory entry to store.

    Returns:
        The ID of the newly inserted row.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO memory
                (user_id, content, memory_type, significance_score, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entry.user_id,
                entry.content,
                entry.memory_type.value,
                entry.significance_score,
                entry.created_at.isoformat(),
            ),
        )
        await db.commit()
        logger.info(
            "Memory stored: user=%s, type=%s, significance=%.2f",
            entry.user_id,
            entry.memory_type.value,
            entry.significance_score,
        )
        return cursor.lastrowid


async def get_user_memory(
    user_id: str,
    memory_type: Optional[MemoryType] = None,
) -> list[MemoryEntry]:
    """
    Retrieve all memory entries for a specific user.

    Args:
        user_id: The user's ID.
        memory_type: Optional filter for STM or LTM only.

    Returns:
        List of memory entries, ordered by most recent first.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if memory_type:
            rows = await db.execute_fetchall(
                """
                SELECT * FROM memory
                WHERE user_id = ? AND memory_type = ?
                ORDER BY created_at DESC
                """,
                (user_id, memory_type.value),
            )
        else:
            rows = await db.execute_fetchall(
                """
                SELECT * FROM memory
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )

        return [
            MemoryEntry(
                id=row["id"],
                user_id=row["user_id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                significance_score=row["significance_score"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


async def clear_user_stm(user_id: str) -> int:
    """
    Clear all Short-Term Memory entries for a user.
    LTM entries are preserved (they represent important facts).

    Args:
        user_id: The user whose STM should be cleared.

    Returns:
        Number of STM entries deleted.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM memory WHERE user_id = ? AND memory_type = ?",
            (user_id, MemoryType.STM.value),
        )
        await db.commit()
        deleted = cursor.rowcount
        logger.info("Cleared %d STM entries for user %s", deleted, user_id)
        return deleted


async def enforce_stm_limit(user_id: str, max_entries: int) -> None:
    """
    Enforce the maximum number of STM entries per user.
    Deletes the oldest STM entries that exceed the limit.

    Args:
        user_id: The user to enforce the limit for.
        max_entries: Maximum STM entries to keep.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM memory
            WHERE id IN (
                SELECT id FROM memory
                WHERE user_id = ? AND memory_type = ?
                ORDER BY created_at DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (user_id, MemoryType.STM.value, max_entries),
        )
        await db.commit()


async def check_db_health() -> bool:
    """
    Check database connectivity by running a simple query.

    Returns:
        True if the database is accessible, False otherwise.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False
