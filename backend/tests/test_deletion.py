"""Investigation deletion tests.

Tests for the investigation deletion service and API endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import UTC, datetime

from app.models import InvestigationStatus


def _make_mock_pool(mock_conn: AsyncMock) -> MagicMock:
    """Create a mock asyncpg pool with proper async context manager for acquire().

    asyncpg's pool.acquire() is a regular method that returns an async context
    manager (not a coroutine). We use MagicMock for pool so that pool.acquire
    is also a MagicMock (not AsyncMock), which correctly returns the acquire_ctx
    without wrapping it in a coroutine.
    """
    pool = MagicMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acquire_ctx
    return pool


def _mock_get_pool(pool):
    """Return a patchable async function that returns the given pool."""
    async def _get_pool():
        return pool
    return _get_pool


class TestDeleteInvestigation:
    """Tests for the delete_investigation service function."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises_value_error(self):
        from app.services.investigation import delete_investigation

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_pool = _make_mock_pool(mock_conn)

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with pytest.raises(ValueError, match="not found"):
                await delete_investigation("nonexistent-id")

    @pytest.mark.asyncio
    async def test_delete_running_investigation_raises_runtime_error(self):
        from app.services.investigation import delete_investigation

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "id": "test-id",
            "status": InvestigationStatus.RUNNING.value,
        }
        mock_pool = _make_mock_pool(mock_conn)

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with pytest.raises(RuntimeError, match="Cannot delete a running investigation"):
                await delete_investigation("test-id")

    @pytest.mark.asyncio
    async def test_delete_captures_report_paths_before_deletion(self):
        from app.services.investigation import delete_investigation

        call_count = 0

        async def fetchrow_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"id": "test-id", "status": InvestigationStatus.CREATED.value}
            return None

        mock_conn = AsyncMock()
        mock_conn.fetchrow = fetchrow_side_effect
        mock_conn.fetch = AsyncMock(return_value=[
            {"file_path": "/path/to/report1.html"},
            {"file_path": "/path/to/report2.pdf"},
        ])
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = _make_mock_pool(mock_conn)

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with patch("app.graph.writer.delete_investigation_graph", new_callable=AsyncMock):
                with patch("pathlib.Path.is_file", return_value=True):
                    with patch("pathlib.Path.unlink") as mock_unlink:
                        result = await delete_investigation("test-id")
                        assert result is True
                        assert mock_unlink.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_neo4j_before_postgresql(self):
        from app.services.investigation import delete_investigation
        call_order = []

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "test-id",
            "status": InvestigationStatus.CREATED.value,
        })
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = _make_mock_pool(mock_conn)

        async def mock_delete_graph(inv_id):
            call_order.append("neo4j")
            return 5

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with patch("app.graph.writer.delete_investigation_graph", side_effect=mock_delete_graph):
                await delete_investigation("test-id")

        assert call_order == ["neo4j"]

    @pytest.mark.asyncio
    async def test_delete_neo4j_failure_still_deletes_postgresql(self):
        from app.services.investigation import delete_investigation

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "test-id",
            "status": InvestigationStatus.CREATED.value,
        })
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = _make_mock_pool(mock_conn)

        async def failing_delete_graph(inv_id):
            raise Exception("Neo4j connection failed")

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with patch("app.graph.writer.delete_investigation_graph", side_effect=failing_delete_graph):
                result = await delete_investigation("test-id")
                assert result is True

    @pytest.mark.asyncio
    async def test_delete_postgresql_failure_raises(self):
        from app.services.investigation import delete_investigation

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "test-id",
            "status": InvestigationStatus.CREATED.value,
        })
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="DELETE 0")
        mock_pool = _make_mock_pool(mock_conn)

        with patch("app.services.investigation.get_pool", _mock_get_pool(mock_pool)):
            with patch("app.graph.writer.delete_investigation_graph", new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="Failed to delete"):
                    await delete_investigation("test-id")


class TestDeleteGraph:
    """Tests for Neo4j graph deletion."""

    @pytest.mark.asyncio
    async def test_delete_investigation_graph(self):
        from app.graph.writer import delete_investigation_graph

        mock_summary = AsyncMock()
        mock_summary.counters.nodes_deleted = 42

        mock_result = AsyncMock()
        mock_result.consume = AsyncMock(return_value=mock_summary)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        # Neo4j driver.session() is a regular method returning an async ctx manager
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_ctx

        async def _mock_get_driver():
            return mock_driver

        with patch("app.graph.writer.get_driver", _mock_get_driver):
            deleted = await delete_investigation_graph("test-investigation-id")
            assert deleted == 42

    @pytest.mark.asyncio
    async def test_delete_empty_investigation_id_raises(self):
        from app.graph.writer import delete_investigation_graph

        with pytest.raises(ValueError, match="non-empty"):
            await delete_investigation_graph("")
