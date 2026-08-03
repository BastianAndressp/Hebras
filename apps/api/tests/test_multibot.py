"""Tests de integración (requieren Postgres real, ver conftest.py::db_conn) que prueban
que dos bots de la misma empresa no cruzan datos: cada uno resuelve su propio
phone_number_id, su propia base de conocimiento y sus propios horarios (migración 0006
corrigió settings para permitir una fila por bot en vez de por empresa)."""
import uuid

import pytest

from app.services import load_bot


@pytest.fixture
async def two_bot_company(db_conn):
    company_id = uuid.uuid4()
    bot_a_id = uuid.uuid4()
    bot_b_id = uuid.uuid4()
    phone_a = f"test-{uuid.uuid4().hex[:12]}"
    phone_b = f"test-{uuid.uuid4().hex[:12]}"

    await db_conn.execute("insert into companies(id, name) values($1, 'Test Multibot Co')", company_id)
    await db_conn.execute(
        """insert into bots(id, company_id, name, phone_number_id, system_prompt)
           values($1, $2, 'Bot A', $3, 'Prompt A, suficientemente largo para pasar validacion')""",
        bot_a_id, company_id, phone_a,
    )
    await db_conn.execute(
        """insert into bots(id, company_id, name, phone_number_id, system_prompt)
           values($1, $2, 'Bot B', $3, 'Prompt B, suficientemente largo para pasar validacion')""",
        bot_b_id, company_id, phone_b,
    )
    await db_conn.execute(
        "insert into knowledge_bases(company_id, bot_id, name) values($1, $2, 'KB A')", company_id, bot_a_id
    )
    await db_conn.execute(
        "insert into knowledge_bases(company_id, bot_id, name) values($1, $2, 'KB B')", company_id, bot_b_id
    )
    await db_conn.execute(
        "insert into settings(company_id, bot_id, out_of_hours_message) values($1, $2, 'Mensaje A')",
        company_id, bot_a_id,
    )
    await db_conn.execute(
        "insert into settings(company_id, bot_id, out_of_hours_message) values($1, $2, 'Mensaje B')",
        company_id, bot_b_id,
    )
    try:
        yield {
            "company_id": company_id,
            "bot_a_id": bot_a_id,
            "bot_b_id": bot_b_id,
            "phone_a": phone_a,
            "phone_b": phone_b,
        }
    finally:
        await db_conn.execute("delete from companies where id=$1", company_id)


async def test_each_bot_resolves_by_its_own_phone_number_id(db_conn, two_bot_company):
    bot_a = await load_bot(db_conn, two_bot_company["phone_a"])
    bot_b = await load_bot(db_conn, two_bot_company["phone_b"])
    assert bot_a["id"] == two_bot_company["bot_a_id"]
    assert bot_b["id"] == two_bot_company["bot_b_id"]
    assert bot_a["id"] != bot_b["id"]


async def test_knowledge_bases_do_not_cross_between_bots(db_conn, two_bot_company):
    kb_a = await db_conn.fetchrow("select * from knowledge_bases where bot_id=$1", two_bot_company["bot_a_id"])
    kb_b = await db_conn.fetchrow("select * from knowledge_bases where bot_id=$1", two_bot_company["bot_b_id"])
    assert kb_a["name"] == "KB A"
    assert kb_b["name"] == "KB B"
    assert kb_a["id"] != kb_b["id"]


async def test_settings_are_independent_per_bot(db_conn, two_bot_company):
    settings_a = await db_conn.fetchrow("select * from settings where bot_id=$1", two_bot_company["bot_a_id"])
    settings_b = await db_conn.fetchrow("select * from settings where bot_id=$1", two_bot_company["bot_b_id"])
    assert settings_a["out_of_hours_message"] == "Mensaje A"
    assert settings_b["out_of_hours_message"] == "Mensaje B"
