"""Disponibilidad y reserva de citas: solapamiento de horarios, fuera de horario
laboral, corrección del bug de timezone (antes check_business_hours comparaba UTC
directo sin aplicar nunca el timezone guardado), y la carrera de reserva concurrente."""
import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from app.booking import SlotUnavailableError, book_appointment, check_slot_available
from app.services import get_local_now


@pytest.fixture
async def bot_with_service(db_conn):
    company_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    service_id = uuid.uuid4()
    await db_conn.execute("insert into companies(id, name) values($1,'Booking Test Co')", company_id)
    await db_conn.execute(
        """insert into bots(id, company_id, name, phone_number_id, system_prompt, status)
           values($1,$2,'Bot de prueba',$3,'Prompt de prueba suficientemente largo para pasar validacion','active')""",
        bot_id, company_id, f"test-booking-{uuid.uuid4().hex[:10]}",
    )
    setting = await db_conn.fetchrow(
        """insert into settings(company_id, bot_id, business_hours_enabled, business_hours)
           values($1,$2,true,$3::jsonb) returning *""",
        company_id, bot_id,
        '{"timezone":"America/Santiago","schedule":{'
        '"mon":{"start":"09:00","end":"18:00","active":true},'
        '"tue":{"start":"09:00","end":"18:00","active":true},'
        '"wed":{"start":"09:00","end":"18:00","active":true},'
        '"thu":{"start":"09:00","end":"18:00","active":true},'
        '"fri":{"start":"09:00","end":"18:00","active":true},'
        '"sat":{"start":"09:00","end":"13:00","active":false},'
        '"sun":{"start":"09:00","end":"13:00","active":false}}}',
    )
    service = await db_conn.fetchrow(
        "insert into services(id, company_id, bot_id, name, duration_minutes) values($1,$2,$3,'Corte',30) returning *",
        service_id, company_id, bot_id,
    )
    bot = await db_conn.fetchrow("select * from bots where id=$1", bot_id)
    try:
        yield bot, setting, service
    finally:
        await db_conn.execute("delete from companies where id=$1", company_id)


def _next_weekday_at(setting, weekday: int, hour: int, minute: int) -> datetime:
    """Próxima fecha (a partir de mañana, para no caer en el pasado) que cae en el día de
    semana pedido, a la hora local del negocio."""
    tz = get_local_now(setting).tzinfo
    now = datetime.now(tz)
    days_ahead = (weekday - now.weekday()) % 7
    days_ahead = days_ahead if days_ahead > 0 else 7
    target = now + timedelta(days=days_ahead)
    return target.replace(hour=hour, minute=minute, second=0, microsecond=0)


async def test_slot_inside_business_hours_with_no_conflict_is_available(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    monday_10am = _next_weekday_at(setting, 0, 10, 0)

    ok, reason = await check_slot_available(db_conn, bot, setting, service, monday_10am)
    assert ok
    assert reason == ""


async def test_slot_outside_business_hours_is_rejected(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    monday_8pm = _next_weekday_at(setting, 0, 20, 0)  # 20:00, fuera del horario 09:00-18:00

    ok, reason = await check_slot_available(db_conn, bot, setting, service, monday_8pm)
    assert not ok
    assert "horario" in reason.lower()


async def test_slot_on_inactive_day_is_rejected(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    saturday_10am = _next_weekday_at(setting, 5, 10, 0)  # sábado, active=false

    ok, reason = await check_slot_available(db_conn, bot, setting, service, saturday_10am)
    assert not ok


async def test_slot_in_the_past_is_rejected(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    yesterday = get_local_now(setting) - timedelta(days=1)

    ok, reason = await check_slot_available(db_conn, bot, setting, service, yesterday)
    assert not ok
    assert "pasó" in reason.lower()


async def test_exact_and_partial_overlaps_are_rejected_adjacent_is_allowed(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    start = _next_weekday_at(setting, 1, 10, 0)  # martes 10:00, servicio de 30 min -> 10:00-10:30
    await book_appointment(db_conn, bot, setting, service, "Cliente A", "56911111111", start)

    # Exacto: mismo horario
    ok, _ = await check_slot_available(db_conn, bot, setting, service, start)
    assert not ok

    # Parcial: empieza 15 min antes, termina dentro del rango ocupado
    ok, _ = await check_slot_available(db_conn, bot, setting, service, start - timedelta(minutes=15))
    assert not ok

    # Adyacente: termina justo cuando empieza la cita ocupada -> debe permitirse
    ok, _ = await check_slot_available(db_conn, bot, setting, service, start - timedelta(minutes=30))
    assert ok

    # Adyacente: empieza justo cuando termina la cita ocupada -> debe permitirse
    ok, _ = await check_slot_available(db_conn, bot, setting, service, start + timedelta(minutes=30))
    assert ok


async def test_timezone_correctness_utc_boundary(db_conn, bot_with_service):
    """9am UTC no siempre son las 9am en America/Santiago (UTC-3 o UTC-4 según DST) --
    fuera de horario ahí aunque "9am" suene como si estuviera dentro de 09:00-18:00 si el
    código comparara todo como UTC sin convertir (el bug que existía antes del fix de
    get_local_now, que ignoraba silenciosamente el timezone guardado)."""
    bot, setting, service = bot_with_service
    monday = _next_weekday_at(setting, 0, 9, 0)  # 09:00 hora de Santiago (correcto, dentro de horario)
    nine_am_utc = monday.astimezone(ZoneInfo("UTC")).replace(hour=9, minute=0)
    nine_am_utc_in_santiago = nine_am_utc.astimezone(ZoneInfo("America/Santiago"))
    # Santiago está siempre detrás de UTC (UTC-3 o UTC-4 según DST), así que 9am UTC cae
    # antes de las 9am hora local -- y por lo tanto fuera del horario 09:00-18:00.
    assert nine_am_utc_in_santiago.hour < 9

    ok, reason = await check_slot_available(db_conn, bot, setting, service, nine_am_utc_in_santiago)
    assert not ok, "9am UTC interpretado en hora local de Santiago debe rechazarse (fuera de 09:00-18:00)"


async def test_concurrent_booking_race_only_one_succeeds(db_conn, bot_with_service):
    bot, setting, service = bot_with_service
    start = _next_weekday_at(setting, 2, 11, 0)  # miércoles 11:00

    from app.db import connect, disconnect, pool
    await connect()
    try:
        async def try_book(name):
            async with pool().acquire() as conn:
                try:
                    await book_appointment(conn, bot, setting, service, name, "56922222222", start)
                    return True
                except SlotUnavailableError:
                    return False

        results = await asyncio.gather(try_book("Cliente 1"), try_book("Cliente 2"))
        assert sorted(results) == [False, True]
    finally:
        await disconnect()
