"""Database models — SQLAlchemy-style table definitions for reference.

Note: We use raw asyncpg for now (simpler, no ORM overhead).
This file documents the expected table shapes for Phase 2+ services.
"""

# This module is intentionally minimal. The actual schema lives in
# app/db/migrations/init.sql. This file exists so that services in
# later phases can import table shape documentation if needed.
