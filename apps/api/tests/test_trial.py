"""Prueba gratuita de 7 días: resolve_account_state deriva el vencimiento al leer (no
hay ningún cron en este proyecto), y get_company_message_limit nunca debe reventar
aunque no haya suscripción — antes eso lanzaba TypeError y tumbaba al worker."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.services import get_company_message_limit, resolve_account_state


@pytest.fixture
async def bare_company(db_conn):
    company_id = uuid.uuid4()
    await db_conn.execute("insert into companies(id, name) values($1, 'Test Trial Co')", company_id)
    try:
        yield company_id
    finally:
        await db_conn.execute("delete from companies where id=$1", company_id)


async def _pro_plan(db_conn):
    return await db_conn.fetchrow("select id, monthly_message_limit from plans where slug='pro'")


async def _insert_subscription(db_conn, company_id, plan_id, status, trial_ends_at=None):
    await db_conn.execute(
        """insert into subscriptions(company_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
           values($1, $2, $3, $4, current_date, current_date + 30)""",
        company_id, plan_id, status, trial_ends_at,
    )


async def test_resolve_account_state_without_subscription_is_blocked_not_error(db_conn, bare_company):
    state = await resolve_account_state(db_conn, bare_company)
    assert state["status"] == "no_subscription"
    assert state["effective_limit"] == 0


async def test_get_company_message_limit_without_subscription_returns_zero(db_conn, bare_company):
    # Regresión directa: antes esto lanzaba TypeError si no había fila de suscripción.
    limit = await get_company_message_limit(db_conn, bare_company, bot_limit=500)
    assert limit == 0


async def test_resolve_account_state_active_trial_uses_trial_cap(db_conn, bare_company):
    plan = await _pro_plan(db_conn)
    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=settings.trial_days)
    await _insert_subscription(db_conn, bare_company, plan["id"], "trialing", trial_ends_at)

    state = await resolve_account_state(db_conn, bare_company)
    assert state["status"] == "trialing"
    assert state["effective_limit"] == min(plan["monthly_message_limit"], settings.trial_message_cap)


async def test_resolve_account_state_expired_trial_is_derived_at_read_time(db_conn, bare_company):
    plan = await _pro_plan(db_conn)
    trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await _insert_subscription(db_conn, bare_company, plan["id"], "trialing", trial_ends_at)

    state = await resolve_account_state(db_conn, bare_company)
    assert state["status"] == "trial_expired"
    assert state["effective_limit"] == 0

    # La fila en la base sigue diciendo 'trialing': no hay cron que la cambie sola, se
    # deriva al leer.
    raw_status = await db_conn.fetchval("select status from subscriptions where company_id=$1", bare_company)
    assert raw_status == "trialing"


async def test_resolve_account_state_active_uses_full_plan_limit(db_conn, bare_company):
    plan = await _pro_plan(db_conn)
    await _insert_subscription(db_conn, bare_company, plan["id"], "active")

    state = await resolve_account_state(db_conn, bare_company)
    assert state["status"] == "active"
    assert state["effective_limit"] == plan["monthly_message_limit"]


async def test_get_company_message_limit_respects_bot_limit_too(db_conn, bare_company):
    plan = await _pro_plan(db_conn)
    await _insert_subscription(db_conn, bare_company, plan["id"], "active")

    # El límite del bot (segundo tope independiente del plan) también debe respetarse.
    limit = await get_company_message_limit(db_conn, bare_company, bot_limit=10)
    assert limit == 10
