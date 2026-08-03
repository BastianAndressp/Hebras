import asyncpg
import pytest

from app.config import settings


@pytest.fixture
async def db_conn():
    """Conexión directa a Postgres para tests de integración (aislamiento multi-tenant,
    multi-bot). Se salta con gracia si no hay base de datos disponible, para que la
    suite de tests unitarios siga corriendo sin Docker."""
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=3)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB no disponible para tests de integración: {exc}")
    try:
        yield conn
    finally:
        await conn.close()
