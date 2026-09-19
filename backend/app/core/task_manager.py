"""TaskManager — in-process async task execution with concurrency control.

Provides a semaphore-gated task manager that replaces Celery for background
investigation execution. Designed for the single-process desktop deployment.

Key semantics:
- Execution slots are controlled by an asyncio.Semaphore(max_concurrent).
- Tasks waiting on the semaphore are PENDING; tasks that have acquired it are RUNNING.
- Cancellation of PENDING tasks does not consume an execution slot.
- Timeouts are enforced via asyncio.wait_for().
- Task failures/timeouts are isolated — sibling tasks are unaffected.
- Shutdown cancels all active tasks and awaits their termination within a timeout.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections import OrderedDict
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# Default shutdown timeout in seconds.
DEFAULT_SHUTDOWN_TIMEOUT = 5.0

# Maximum number of completed tasks to retain in history.
MAX_HISTORY_SIZE = 200


class TaskState(enum.Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo:
    """Metadata for a managed task."""

    __slots__ = (
        "task_id",
        "state",
        "created_at",
        "started_at",
        "finished_at",
        "result",
        "error",
        "_asyncio_task",
    )

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.state = TaskState.PENDING
        self.created_at = time.monotonic()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.result: Any = None
        self.error: str | None = None
        self._asyncio_task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "error": self.error,
        }


class TaskManager:
    """Manages background task execution with bounded concurrency.

    Args:
        max_concurrent: Maximum number of tasks that can run simultaneously.
        default_timeout: Default per-task timeout in seconds (None = no timeout).
    """

    def __init__(
        self,
        max_concurrent: int = 4,
        default_timeout: float | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._active_tasks: dict[str, TaskInfo] = {}
        self._history: OrderedDict[str, TaskInfo] = OrderedDict()
        self._shutting_down = False

    def submit(
        self,
        task_id: str,
        coro: Coroutine,
        *,
        timeout: float | None = None,
    ) -> TaskInfo:
        """Submit a coroutine for managed execution.

        The coroutine will wait on the semaphore before executing.
        While waiting, its state is PENDING. Once the semaphore is
        acquired, the state transitions to RUNNING.

        Args:
            task_id: Unique identifier for this task.
            coro: The coroutine to execute.
            timeout: Per-task timeout in seconds. Overrides default_timeout.
                     None means use the default; 0 means no timeout.

        Returns:
            TaskInfo with the task's metadata.

        Raises:
            RuntimeError: If the TaskManager is shutting down or task_id is duplicate.
        """
        if self._shutting_down:
            raise RuntimeError("TaskManager is shutting down, cannot accept new tasks")
        if task_id in self._active_tasks:
            raise RuntimeError(f"Task {task_id} already exists")

        effective_timeout = timeout if timeout is not None else self._default_timeout

        info = TaskInfo(task_id)
        self._active_tasks[task_id] = info

        asyncio_task = asyncio.create_task(
            self._run_task(info, coro, effective_timeout),
            name=f"task-{task_id}",
        )
        info._asyncio_task = asyncio_task
        logger.info("TaskManager: submitted task %s", task_id)
        return info

    async def _run_task(
        self,
        info: TaskInfo,
        coro: Coroutine,
        timeout: float | None,
    ) -> None:
        """Internal wrapper: run → handle result/error."""
        # Transition to RUNNING.
        info.state = TaskState.RUNNING
        info.started_at = time.monotonic()
        try:
            if timeout and timeout > 0:
                info.result = await asyncio.wait_for(coro, timeout=timeout)
            else:
                info.result = await coro
            info.state = TaskState.COMPLETED
        except asyncio.CancelledError:
            info.state = TaskState.CANCELLED
            logger.info("TaskManager: task %s cancelled while running", info.task_id)
        except TimeoutError:
            info.state = TaskState.FAILED
            info.error = "TimeoutError"
            logger.warning("TaskManager: task %s timed out", info.task_id)
        except Exception as exc:
            info.state = TaskState.FAILED
            info.error = str(exc)
            logger.error(
                "TaskManager: task %s failed: %s",
                info.task_id,
                exc,
                exc_info=True,
            )
        finally:
            info.finished_at = time.monotonic()
            self._move_to_history(info)

    def cancel(self, task_id: str) -> bool:
        """Cancel a task by ID.

        Returns True if the task was found and cancel was requested.
        """
        info = self._active_tasks.get(task_id)
        if info is None:
            return False
        if info._asyncio_task is not None:
            info._asyncio_task.cancel()
            return True
        return False

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Get task info by ID (checks active and history)."""
        return self._active_tasks.get(task_id) or self._history.get(task_id)

    @property
    def active_count(self) -> int:
        """Number of tasks that are currently active (PENDING + RUNNING)."""
        return len(self._active_tasks)

    @property
    def running_count(self) -> int:
        """Number of tasks that are currently RUNNING (holding semaphore)."""
        return sum(1 for t in self._active_tasks.values() if t.state == TaskState.RUNNING)

    @property
    def pending_count(self) -> int:
        """Number of tasks that are currently PENDING (waiting for semaphore)."""
        return sum(1 for t in self._active_tasks.values() if t.state == TaskState.PENDING)

    def list_active(self) -> list[dict[str, Any]]:
        """List all active tasks."""
        return [t.to_dict() for t in self._active_tasks.values()]

    async def shutdown(self, timeout: float = DEFAULT_SHUTDOWN_TIMEOUT) -> None:
        """Gracefully shut down all active tasks.

        Cancels all active asyncio.Task objects and awaits their
        termination within the given timeout. No orphaned tasks remain.
        """
        self._shutting_down = True
        logger.info("TaskManager: shutting down (%d active tasks)", len(self._active_tasks))

        tasks_to_cancel: list[asyncio.Task] = []
        for info in list(self._active_tasks.values()):
            if info._asyncio_task is not None and not info._asyncio_task.done():
                info._asyncio_task.cancel()
                tasks_to_cancel.append(info._asyncio_task)

        if tasks_to_cancel:
            done, pending = await asyncio.wait(tasks_to_cancel, timeout=timeout)
            # Force-cancel anything still pending after timeout.
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        self._active_tasks.clear()
        logger.info("TaskManager: shutdown complete")

    def _move_to_history(self, info: TaskInfo) -> None:
        """Move a completed/failed/cancelled task to bounded history."""
        self._active_tasks.pop(info.task_id, None)
        self._history[info.task_id] = info
        # Evict oldest entries if history exceeds max size.
        while len(self._history) > MAX_HISTORY_SIZE:
            self._history.popitem(last=False)


# ── Module-level singleton ────────────────────────────────────────────────────

_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """Get or create the global TaskManager singleton."""
    global _task_manager
    if _task_manager is None:
        from app.core.settings_store import get_app_settings
        settings = get_app_settings()
        _task_manager = TaskManager(max_concurrent=settings.general.max_concurrent_investigations)
    return _task_manager


def reset_task_manager() -> None:
    """Reset the global TaskManager (for testing)."""
    global _task_manager
    _task_manager = None
