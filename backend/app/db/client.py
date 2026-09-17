"""Database client — aiosqlite wrapper for asyncpg migration compatibility."""

from collections.abc import AsyncGenerator
import functools
import os
import re
import aiosqlite

from app.core.config import get_settings

_db_path: str | None = None

def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


def get_db_path() -> str:
    global _db_path
    if _db_path is None:
        if "PYTEST_CURRENT_TEST" in os.environ:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            _db_path = os.path.join(data_dir, "osint_nexus_test2.osint")
        else:
            raise RuntimeError("No active workspace")
    return _db_path


class AsyncpgCompatibleConnection:
    """Wraps an aiosqlite connection to mimic asyncpg's API and translate SQL."""
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        self._conn.row_factory = aiosqlite.Row

    @staticmethod
    @functools.lru_cache(maxsize=1024)
    def _translate_sql(sql: str) -> str:
        # Translate Postgres $1, $2 to SQLite ?1, ?2 to preserve order.
        sql = re.sub(r'\$(\d+)', r'?\1', sql)
        sql = sql.replace("::text[]", "")
        sql = sql.replace("::uuid[]", "")
        sql = sql.replace("::jsonb", "")
        sql = sql.replace("::text", "")
        sql = sql.replace("::uuid", "")
        sql = sql.replace("ILIKE", "LIKE")
        # Replace ANY(?N) with JSON each for SQLite array simulation
        sql = re.sub(r'=\s*ANY\(\?(\d+)\)', r'IN (SELECT value FROM json_each(?\1))', sql)
        sql = sql.replace("NOW()", "datetime('now', 'utc')")
        return sql

    def _prepare_args(self, args):
        """Serialize lists to JSON strings to support SQLite json_each for arrays."""
        import json
        prepared = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                prepared.append(json.dumps(arg))
            else:
                prepared.append(arg)
        return prepared

    class RecordProxy:
        def __init__(self, row):
            import datetime
            self._row = row
            self._parsed = {}
            for k in row.keys():
                val = row[k]
                # Convert timestamp strings to datetime objects to mimic asyncpg
                if isinstance(val, str) and (k.endswith('_at') or k == 'timestamp'):
                    try:
                        # SQLite datetime('now', 'utc') returns 'YYYY-MM-DD HH:MM:SS'
                        if len(val) == 19:
                            self._parsed[k] = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                        else:
                            self._parsed[k] = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
                    except ValueError:
                        self._parsed[k] = val
                else:
                    self._parsed[k] = val

        def __getitem__(self, key):
            if isinstance(key, int):
                # Integer access: get the key at that index
                key = list(self._row.keys())[key]
            return self._parsed[key]

        def keys(self):
            return self._parsed.keys()
            
        def get(self, key, default=None):
            return self._parsed.get(key, default)
            
        def __iter__(self):
            return iter(self._parsed)
            
        def __len__(self):
            return len(self._parsed)

    def _wrap_row(self, row):
        if row is None:
            return None
        return self.RecordProxy(row)

    def _wrap_rows(self, rows):
        return [self._wrap_row(r) for r in rows]

    async def fetch(self, query: str, *args):
        query = self._translate_sql(query)
        args = self._prepare_args(args)
        async with self._conn.execute(query, args) as cursor:
            return self._wrap_rows(await cursor.fetchall())

    async def fetchrow(self, query: str, *args):
        query = self._translate_sql(query)
        args = self._prepare_args(args)
        async with self._conn.execute(query, args) as cursor:
            return self._wrap_row(await cursor.fetchone())

    async def fetchval(self, query: str, *args):
        query = self._translate_sql(query)
        args = self._prepare_args(args)
        async with self._conn.execute(query, args) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

    import contextlib

    @contextlib.asynccontextmanager
    async def transaction(self):
        """Provide explicit BEGIN/COMMIT transaction blocks.
        
        Since isolation_level=None is used globally for autocommit, 
        this allows explicit atomic grouped writes.
        """
        await self._conn.execute("BEGIN")
        try:
            yield
            await self._conn.execute("COMMIT")
        except Exception:
            await self._conn.execute("ROLLBACK")
            raise

    async def execute(self, query: str, *args) -> str:
        query = self._translate_sql(query)
        args = self._prepare_args(args)
        await self._conn.execute(query, args)
        await self._conn.commit()


class AsyncpgCompatiblePoolContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return AsyncpgCompatibleConnection(self._conn)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AsyncpgCompatiblePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return AsyncpgCompatiblePoolContext(self._conn)
        
    async def close(self):
        await self._conn.close()


_pool_conn: aiosqlite.Connection | None = None
_pool: AsyncpgCompatiblePool | None = None

async def _init_schema(conn: aiosqlite.Connection) -> None:
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        schema_path = os.path.join(sys._MEIPASS, "app", "db", "schema.sql")
    else:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
            
            # Auto-heal edges_bidi if migrating from older schema
            try:
                await conn.execute("ALTER TABLE edges_bidi ADD COLUMN investigation_id TEXT NOT NULL DEFAULT ''")
                await conn.commit()
            except Exception:
                pass
                
            try:
                await conn.executescript(schema_sql)
            except Exception as e:
                import logging
                logging.warning(f"Schema init issue: {e}")
            await conn.commit()

async def get_pool():
    global _pool_conn, _pool
    if _pool is None:
        db_path = get_db_path()
        is_new = not os.path.exists(db_path)
        
        _pool_conn = await aiosqlite.connect(db_path, isolation_level=None)
        
        # Register missing Postgres functions
        from uuid import uuid4
        await _pool_conn.create_function("gen_random_uuid", 0, lambda: str(uuid4()))
        
        # Security and concurrency PRAGMAs
        await _pool_conn.execute("PRAGMA journal_mode=WAL")
        await _pool_conn.execute("PRAGMA busy_timeout=5000")
        await _pool_conn.execute("PRAGMA synchronous=NORMAL")
        await _pool_conn.execute("PRAGMA foreign_keys=ON")
        await _pool_conn.execute("PRAGMA trusted_schema=OFF")
        
        # Always run schema to ensure new tables (like workspace_reports) are added
        # to existing databases. schema.sql uses IF NOT EXISTS safely.
        await _init_schema(_pool_conn)
            
        _pool = AsyncpgCompatiblePool(_pool_conn)
    return _pool

async def close_pool() -> None:
    global _pool, _pool_conn
    if _pool_conn:
        await _pool_conn.close()
        _pool_conn = None
        _pool = None

def reset_pool() -> None:
    global _pool, _pool_conn, _db_path
    _pool = None
    _pool_conn = None
    _db_path = None

async def get_db() -> AsyncGenerator[AsyncpgCompatibleConnection, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
