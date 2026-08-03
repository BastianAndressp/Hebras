"""Anti-abuso: la barrera dura es el número de WhatsApp (un número ya usado no vuelve a
dar prueba); la IP es solo señal blanda (contadores, nunca bloqueo permanente).

Nota de alcance: esta suite no levanta un TestClient HTTP (el proyecto no usa uno en
ningún test existente) — prueba la lógica de conteo/decisión directamente contra la
base de datos real, que es lo que auth_router.py::signup usa para decidir el 429. El
comportamiento HTTP completo (curl -> 429 en el 4º registro desde la misma IP) se
verificó manualmente contra el stack corriendo en Docker."""
import uuid

import pytest

from app.antiabuse import count_recent_trials_for_ip, is_disposable_email, total_trials_for_ip
from app.services import PLACEHOLDER_PHONE_PREFIX, enforce_whatsapp_trial_claim, is_placeholder_number


def test_is_disposable_email_detects_known_domains():
    assert is_disposable_email("test@mailinator.com")
    assert is_disposable_email("Test@Mailinator.com")  # sin distinguir mayúsculas
    assert not is_disposable_email("test@gmail.com")


def test_is_disposable_email_handles_malformed_input():
    assert not is_disposable_email("no-es-un-correo")
    assert not is_disposable_email("")


def test_is_placeholder_number():
    assert is_placeholder_number(None)
    assert is_placeholder_number("")
    assert is_placeholder_number(f"{PLACEHOLDER_PHONE_PREFIX}{uuid.uuid4()}")
    assert not is_placeholder_number("558299991234")


@pytest.fixture
async def two_trialing_companies(db_conn):
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    plan = await db_conn.fetchrow("select id from plans where slug='pro'")
    for cid, name in ((company_a, "Claim Test A"), (company_b, "Claim Test B")):
        await db_conn.execute("insert into companies(id, name) values($1,$2)", cid, name)
        await db_conn.execute(
            """insert into subscriptions(company_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
               values($1, $2, 'trialing', now() + interval '7 days', current_date, current_date + 30)""",
            cid, plan["id"],
        )
    try:
        yield company_a, company_b
    finally:
        await db_conn.execute("delete from companies where id = any($1::uuid[])", [company_a, company_b])


async def test_first_claim_of_a_number_keeps_the_trial(db_conn, two_trialing_companies):
    company_a, _ = two_trialing_companies
    phone = f"test-{uuid.uuid4().hex[:10]}"

    await enforce_whatsapp_trial_claim(db_conn, company_a, phone)

    status = await db_conn.fetchval("select status from subscriptions where company_id=$1", company_a)
    assert status == "trialing"
    claim_owner = await db_conn.fetchval("select company_id from whatsapp_number_claims where phone_number_id=$1", phone)
    assert str(claim_owner) == str(company_a)


async def test_reusing_a_claimed_number_expires_only_the_new_companys_trial(db_conn, two_trialing_companies):
    company_a, company_b = two_trialing_companies
    phone = f"test-{uuid.uuid4().hex[:10]}"

    await enforce_whatsapp_trial_claim(db_conn, company_a, phone)
    await enforce_whatsapp_trial_claim(db_conn, company_b, phone)

    status_b = await db_conn.fetchval("select status from subscriptions where company_id=$1", company_b)
    assert status_b == "trial_expired"
    # A, la dueña original del número, no se ve afectada.
    status_a = await db_conn.fetchval("select status from subscriptions where company_id=$1", company_a)
    assert status_a == "trialing"


async def test_reclaiming_own_number_does_not_expire_own_trial(db_conn, two_trialing_companies):
    company_a, _ = two_trialing_companies
    phone = f"test-{uuid.uuid4().hex[:10]}"

    await enforce_whatsapp_trial_claim(db_conn, company_a, phone)
    await enforce_whatsapp_trial_claim(db_conn, company_a, phone)  # de nuevo, misma empresa

    status = await db_conn.fetchval("select status from subscriptions where company_id=$1", company_a)
    assert status == "trialing"


async def test_placeholder_numbers_are_never_claimed(db_conn, two_trialing_companies):
    company_a, _ = two_trialing_companies
    placeholder = f"{PLACEHOLDER_PHONE_PREFIX}{uuid.uuid4()}"

    await enforce_whatsapp_trial_claim(db_conn, company_a, placeholder)

    claimed = await db_conn.fetchval(
        "select count(*) from whatsapp_number_claims where phone_number_id=$1", placeholder
    )
    assert claimed == 0


@pytest.fixture
async def signup_events_ip(db_conn):
    ip_hash = f"test-hash-{uuid.uuid4().hex}"
    created_company_ids: list = []
    try:
        yield ip_hash, created_company_ids
    finally:
        await db_conn.execute("delete from signup_events where ip_hash=$1", ip_hash)
        if created_company_ids:
            await db_conn.execute("delete from companies where id = any($1::uuid[])", created_company_ids)


async def test_ip_counters_ignore_rows_without_company(db_conn, signup_events_ip):
    ip_hash, _ = signup_events_ip
    # Un reenvío de código (usuario ya existía, sin empresa nueva) no debe contar.
    await db_conn.execute("insert into signup_events(email, ip_hash, company_id) values($1,$2,null)", "a@example.com", ip_hash)

    assert await count_recent_trials_for_ip(db_conn, ip_hash) == 0
    assert await total_trials_for_ip(db_conn, ip_hash) == 0


async def test_ip_counters_count_rows_with_company(db_conn, signup_events_ip):
    ip_hash, created = signup_events_ip
    company_id = uuid.uuid4()
    await db_conn.execute("insert into companies(id, name) values($1,'Signup Event Co')", company_id)
    created.append(company_id)
    await db_conn.execute("insert into signup_events(email, ip_hash, company_id) values($1,$2,$3)", "b@example.com", ip_hash, company_id)

    assert await count_recent_trials_for_ip(db_conn, ip_hash) == 1
    assert await total_trials_for_ip(db_conn, ip_hash) == 1
