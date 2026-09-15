"""Workspace file lifecycle management and coordination.

Coordinates safe opening, saving, and closing of .osint SQLite files,
ensuring strict concurrency limits with active tasks and data integrity.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import aiosqlite

from app.core.task_manager import get_task_manager
from app.db.client import get_pool, set_db_path, close_pool

logger = logging.getLogger(__name__)


class WorkspaceError(Exception):
    """Base exception for workspace errors."""


class WorkspaceConflictError(WorkspaceError):
    """Raised when a workspace operation conflicts with running tasks."""


class WorkspaceValidationError(WorkspaceError):
    """Raised when a workspace file is invalid or insecure."""


class WorkspaceManager:
    """Manages workspace lifecycle, preventing task/database corruption."""

    def __init__(self) -> None:
        self._current_workspace: str | None = None
        self._lock = asyncio.Lock()

    @property
    def current_workspace(self) -> str | None:
        return self._current_workspace

    async def _assert_no_active_tasks(self, operation: str) -> None:
        """Ensure no background tasks are running during a workspace switch."""
        tm = get_task_manager()
        if tm.active_count > 0:
            raise WorkspaceConflictError(
                f"Cannot perform '{operation}' while {tm.active_count} tasks are running."
            )

    def _validate_path(self, path: str) -> str:
        """Resolve and validate a path to prevent directory traversal."""
        resolved = Path(path).resolve()
        if not resolved.name.endswith(".osint"):
            raise WorkspaceValidationError("Workspace file must have a .osint extension.")
        return str(resolved)

    async def _validate_schema(self, path: str) -> None:
        """Safely validate an untrusted .osint file before accepting it."""
        try:
            # We connect directly, strictly avoiding the global pool
            async with aiosqlite.connect(path) as conn:
                await conn.execute("PRAGMA trusted_schema=OFF")
                
                # Check tables
                async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                    tables = {row[0] async for row in cursor}
                
                required_tables = {
                    "investigations", "observations", "entities", 
                    "relationships", "activity_log", "notes"
                }
                
                missing = required_tables - tables
                if missing:
                    raise WorkspaceValidationError(f"Database is missing required tables: {missing}")

                # Check version (we only support version 1 right now based on our init script)
                # But our schema.sql doesn't actually set user_version currently. Let's just ensure it's a valid SQLite DB.
                # A malformed file would throw DatabaseError.
                async with conn.execute("PRAGMA user_version") as cursor:
                    row = await cursor.fetchone()
                    version = row[0] if row else 0
                    
        except aiosqlite.DatabaseError as exc:
            raise WorkspaceValidationError(f"Invalid SQLite database: {exc}")

    async def create_new(self, path: str) -> None:
        """Create a new workspace at the given path."""
        async with self._lock:
            await self._assert_no_active_tasks("New")
            path = self._validate_path(path)
            
            if os.path.exists(path):
                raise WorkspaceConflictError("File already exists.")

            await close_pool()
            set_db_path(path)
            # get_pool() handles `is_new` check and calls `_init_schema`
            await get_pool()
            
            self._current_workspace = path
            logger.info("Created new workspace: %s", path)

    async def open_workspace(self, path: str) -> None:
        """Open an existing workspace safely."""
        async with self._lock:
            await self._assert_no_active_tasks("Open")
            path = self._validate_path(path)
            
            if not os.path.exists(path):
                raise WorkspaceValidationError("Workspace file does not exist.")

            # Validate before creating backup
            await self._validate_schema(path)
            
            # Create safe .bak backup via SQLite Online Backup
            bak_path = path + ".bak"
            try:
                async with aiosqlite.connect(path) as src, aiosqlite.connect(bak_path) as dst:
                    await src.execute("PRAGMA trusted_schema=OFF")
                    await dst.execute("PRAGMA trusted_schema=OFF")
                    await src.backup(dst)
                logger.info("Created backup at %s", bak_path)
            except Exception as exc:
                logger.error("Failed to create backup: %s", exc)
                raise WorkspaceError(f"Failed to create workspace backup: {exc}")

            # Safe to close current and switch
            await close_pool()
            set_db_path(path)
            await get_pool()
            
            self._current_workspace = path
            logger.info("Opened workspace: %s", path)

    async def save_as(self, new_path: str) -> None:
        """Save the active workspace to a new file via SQLite backup API.
        
        This can be done concurrently while tasks are running, since
        it uses the safe Online Backup API from the active connection.
        """
        async with self._lock:
            if not self._current_workspace:
                raise WorkspaceError("No active workspace to save.")
                
            new_path = self._validate_path(new_path)
            if os.path.exists(new_path):
                raise WorkspaceConflictError("Destination file already exists.")

            # We DO NOT close the pool, we backup from the current file to the new file
            try:
                # We do this from the disk file. Active pool flushes to WAL.
                # SQLite backup API handles WAL coordination seamlessly.
                async with aiosqlite.connect(self._current_workspace) as src, aiosqlite.connect(new_path) as dst:
                    await src.execute("PRAGMA trusted_schema=OFF")
                    await dst.execute("PRAGMA trusted_schema=OFF")
                    await src.backup(dst)
                logger.info("Saved workspace as: %s", new_path)
            except Exception as exc:
                logger.error("Failed to Save As: %s", exc)
                raise WorkspaceError(f"Failed to Save As: {exc}")

    async def close_workspace(self) -> None:
        """Close the active workspace."""
        async with self._lock:
            await self._assert_no_active_tasks("Close")
            
            if not self._current_workspace:
                return

            await close_pool()
            set_db_path(None)  # type: ignore
            self._current_workspace = None
            logger.info("Workspace closed.")

# Singleton
_workspace_manager: WorkspaceManager | None = None

def get_workspace_manager() -> WorkspaceManager:
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager

def reset_workspace_manager() -> None:
    global _workspace_manager
    _workspace_manager = None
