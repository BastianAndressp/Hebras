import json
from contextlib import asynccontextmanager

import asyncpg
from .config import settings


_pool: asyncpg.Pool | None = None
_tenant_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Sin esto, asyncpg NO decodifica columnas jsonb/json a dict/list de Python -- las
    devuelve como texto crudo. Eso hacía que check_business_hours (isinstance(bh, dict))
    fallara en silencio siempre que business_hours_enabled estuviera activo, sin ningún
    error visible: la comparación de horario simplemente nunca se ejecutaba."""
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")


async def connect() -> None:
    global _pool, _tenant_pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10, init=_init_connection)
    _tenant_pool = await asyncpg.create_pool(settings.tenant_database_url, min_size=1, max_size=10, init=_init_connection)


async def disconnect() -> None:
    global _pool, _tenant_pool
    if _pool:
        await _pool.close()
        _pool = None
    if _tenant_pool:
        await _tenant_pool.close()
        _tenant_pool = None


def pool() -> asyncpg.Pool:
    """Pool con privilegios elevados (bypassa RLS). Reservado para procesos internos sin
    Principal: webhook de Meta, worker, auth (signup/login), bootstrap. Nunca usar en una
    ruta autenticada del dashboard — usar tenant_conn() en su lugar."""
    if not _pool:
        raise RuntimeError("database pool has not been initialized")
    return _pool


def tenant_pool() -> asyncpg.Pool:
    if not _tenant_pool:
        raise RuntimeError("tenant database pool has not been initialized")
    return _tenant_pool


@asynccontextmanager
async def tenant_conn(company_id: str):
    """Conexión con el rol app_user (sin BYPASSRLS) con request.jwt.claims seteado para
    esta transacción, de modo que la RLS forzada en las tablas de tenant (migración 0005)
    realmente filtre por company_id a nivel de base de datos, no solo en la query de la app."""
    async with tenant_pool().acquire() as conn:
        async with conn.transaction():
            claims = json.dumps({"company_id": company_id})
            await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
            yield conn

