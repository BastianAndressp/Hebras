"""Tool-calling en el flujo de citas: el loop de generate_reply() ejecuta la tool y
sigue la conversación con su resultado; y un error dentro de una tool (ej. horario ya
tomado) nunca debe tumbar worker.process() -- debe volver como {"error": ...} para que
el modelo responda en lenguaje natural."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services import generate_reply
from app.worker import process


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _tool_call_response(name, arguments):
    return _FakeResponse({
        "choices": [{"message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_1", "function": {"name": name, "arguments": arguments}}],
        }}],
        "usage": {"total_tokens": 10},
    })


def _final_text_response(text):
    return _FakeResponse({
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"total_tokens": 5},
    })


async def test_generate_reply_tool_loop_calls_executor_and_continues():
    """El modelo pide check_availability, la tool responde, y el modelo termina en
    texto -- generate_reply debe devolver ese texto final, no el tool_call crudo."""
    bot = {"system_prompt": "Eres un asistente.", "model": "fake/model", "fallback_model": None,
           "temperature": 0.4, "max_tokens": 400}
    tool_executor = AsyncMock(return_value={"available": True})
    responses = [
        _tool_call_response("check_availability", '{"service_name":"Corte","date":"2026-01-01","time":"10:00"}'),
        _final_text_response("¡Sí, tengo disponible a las 10:00!"),
    ]

    async def fake_post(self, url, headers, json):
        return responses.pop(0)

    with patch("httpx.AsyncClient.post", fake_post):
        reply, tokens, cost = await generate_reply(
            bot, [{"role": "user", "content": "quiero un corte mañana a las 10"}],
            tools=[{"type": "function", "function": {"name": "check_availability"}}],
            tool_executor=tool_executor,
        )

    assert reply == "¡Sí, tengo disponible a las 10:00!"
    tool_executor.assert_awaited_once_with("check_availability", {"service_name": "Corte", "date": "2026-01-01", "time": "10:00"})


async def test_generate_reply_without_tools_is_unaffected():
    """Regresión: bots sin tools configuradas siguen funcionando exactamente igual que
    antes (una sola llamada, sin loop)."""
    bot = {"system_prompt": "Eres un asistente.", "model": "fake/model", "fallback_model": None,
           "temperature": 0.4, "max_tokens": 400}

    async def fake_post(self, url, headers, json):
        assert "tools" not in json
        return _final_text_response("Hola, ¿en qué te ayudo?")

    with patch("httpx.AsyncClient.post", fake_post):
        reply, tokens, cost = await generate_reply(bot, [{"role": "user", "content": "hola"}])

    assert reply == "Hola, ¿en qué te ayudo?"


@pytest.fixture
async def active_account_with_service(db_conn):
    company_id = uuid.uuid4()
    bot_id = uuid.uuid4()
    service_id = uuid.uuid4()
    phone_number_id = f"test-tools-{uuid.uuid4().hex[:10]}"
    contact_phone = "56933333333"

    await db_conn.execute("insert into companies(id, name) values($1,'Tool Test Co')", company_id)
    plan = await db_conn.fetchrow("select id, monthly_message_limit from plans where slug='pro'")
    await db_conn.execute(
        """insert into subscriptions(company_id, plan_id, status, current_period_start, current_period_end)
           values($1,$2,'active',current_date,current_date+30)""",
        company_id, plan["id"],
    )
    await db_conn.execute(
        """insert into bots(id, company_id, name, phone_number_id, system_prompt, status)
           values($1,$2,'Bot de prueba',$3,'Prompt de prueba suficientemente largo para pasar validacion','active')""",
        bot_id, company_id, phone_number_id,
    )
    await db_conn.execute(
        "insert into services(id, company_id, bot_id, name, duration_minutes) values($1,$2,$3,'Corte',30)",
        service_id, company_id, bot_id,
    )
    try:
        yield {"company_id": company_id, "bot_id": bot_id, "service_id": service_id,
               "phone_number_id": phone_number_id, "contact_phone": contact_phone}
    finally:
        await db_conn.execute("delete from companies where id=$1", company_id)


async def test_tool_executor_error_never_crashes_process(db_conn, active_account_with_service):
    """El tool_executor que arma worker.py debe capturar SlotUnavailableError (u otro
    error) y devolver {"error": ...}, no propagar la excepción -- process() debe
    terminar limpio igual."""
    from app.db import connect, disconnect

    async def fake_generate_reply(bot, history, knowledge_context="", custom_api_key=None,
                                   tools=None, tool_executor=None, max_tool_rounds=3):
        assert tool_executor is not None, "el bot tiene un servicio activo, tools debía pasarse"
        # Fecha/hora mal formada a propósito para forzar InvalidBookingRequestError
        # dentro del tool_executor real de worker.py, y confirmar que no se propaga.
        result = await tool_executor("book_appointment", {
            "service_name": "Corte", "date": "fecha-invalida", "time": "10:00", "customer_name": "Cliente",
        })
        assert "error" in result
        return "Disculpa, no entendí bien la fecha, ¿me la puedes repetir?", 10, 0.0

    await connect()
    try:
        with patch("app.worker.generate_reply", fake_generate_reply), \
             patch("app.worker.send_whatsapp", AsyncMock()):
            await process({
                "meta_message_id": f"test-{uuid.uuid4().hex}",
                "phone_number_id": active_account_with_service["phone_number_id"],
                "contact_phone": active_account_with_service["contact_phone"],
                "text": "quiero agendar un corte",
                "timestamp": None,
            })
    finally:
        await disconnect()
