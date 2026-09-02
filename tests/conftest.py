"""
Pytest shared fixtures & environment bootstrap.

Creates an isolated SQLite database for every test run so integration tests
never touch the development database (stress_ai.db).
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

TEST_DB_PATH = "/tmp/stress_ai_test.db"
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

from backend.app.core.database import engine, Base  # noqa: E402
from backend.app import models as _models  # noqa: F401, E402  (register all tables)

def create_test_tables():
    import asyncio
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_create())

create_test_tables()