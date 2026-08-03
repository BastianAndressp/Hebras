"""Regresión del bug de handoff permanente: antes, el bloqueo por facturación (trial
vencido, sin suscripción, cuota agotada) caía en la misma rama que la derivación a
humano y marcaba conversations.status='handoff' — dejando la conversación muerta para
el bot incluso después de que la empresa pagara. Ahora el bloqueo por facturación nunca
toca conversations.status.

Va contra la Postgres real vía worker.process() (no mockeado): usa el pool elevado de
la app (app.db.connect/pool), no la conexión de la fixture db_conn, para ejercitar
exactamente el mismo código que corre en producción."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db import connect, disconnect, pool
from app.worker import process


@pytest.fixture
async def blocked_account(db_conn):
    company_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    phone_number_id = f"test-blocked-{uuid.uuid4().hex[:10]}"
    contact_phone = "56900000000"

    await db_conn.execute("insert into companies(id, name) values($1,'Worker Block Test')", company_id)
    plan = await db_conn.fetchrow("select id from plans where slug='pro'")
    trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_conn.execute(
        """insert into subscriptions(company_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
           values($1, $2, 'trialing', $3, current_date, current_date + 30)""",
        company_id, plan["id"], trial_ends_at,
    )
    await db_conn.execute(
        """insert into bots(id, company_id, name, phone_number_id, system_prompt, status)
           values($1, $2, 'Bot de prueba', $3, 'Prompt de prueba suficientemente largo para pasar validacion', 'active')""",
        bot_id, company_id, phone_number_id,
    )
    try:
        yield {
            "company_id": company_id,
            "bot_id": bot_id,
            "phone_number_id": phone_number_id,
            "contact_phone": contact_phone,
        }
    finally:
        await db_conn.execute("delete from companies where id=$1", company_id)


async def test_blocked_account_does_not_reply_and_does_not_mark_handoff(blocked_account):
    await connect()
    try:
        payload = {
            "meta_message_id": f"test-{uuid.uuid4().hex}",
            "phone_number_id": blocked_account["phone_number_id"],
            "contact_phone": blocked_account["contact_phone"],
            "text": "hola, quiero información",
            "timestamp": None,
        }

        await process(payload)  # no debe lanzar, y no debe intentar llamar a WhatsApp/OpenRouter

        async with pool().acquire() as conn:
            conversation = await conn.fetchrow(
                "select status from conversations where bot_id=$1 and contact_phone=$2",
                blocked_account["bot_id"], blocked_account["contact_phone"],
            )
            assert conversation is not None
            assert conversation["status"] != "handoff"

            notif_count = await conn.fetchval(
                "select count(*) from notifications where company_id=$1 and title='Bot pausado por facturación'",
                blocked_account["company_id"],
            )
            assert notif_count == 1
    finally:
        await disconnect()


async def test_blocked_account_notification_is_not_duplicated_per_message(blocked_account):
    await connect()
    try:
        for i in range(3):
            await process({
                "meta_message_id": f"test-{uuid.uuid4().hex}",
                "phone_number_id": blocked_account["phone_number_id"],
                "contact_phone": blocked_account["contact_phone"],
                "text": f"mensaje {i}",
                "timestamp": None,
            })

        async with pool().acquire() as conn:
            notif_count = await conn.fetchval(
                "select count(*) from notifications where company_id=$1 and title='Bot pausado por facturación'",
                blocked_account["company_id"],
            )
            assert notif_count == 1
    finally:
        await disconnect()
