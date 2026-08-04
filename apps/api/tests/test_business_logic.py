from app.services import check_business_hours, should_handoff


class FakeConn:
    def __init__(self, fetchrow_result=None, fetch_result=None):
        self._fetchrow_result = fetchrow_result
        self._fetch_result = fetch_result or []

    async def fetchrow(self, query, *args):
        return self._fetchrow_result

    async def fetch(self, query, *args):
        return self._fetch_result


async def test_check_business_hours_disabled_returns_in_hours():
    conn = FakeConn(fetchrow_result={"business_hours_enabled": False})
    is_out, msg = await check_business_hours(conn, "bot-1")
    assert is_out is False
    assert msg == ""


async def test_check_business_hours_no_setting_row_returns_in_hours():
    conn = FakeConn(fetchrow_result=None)
    is_out, _ = await check_business_hours(conn, "bot-1")
    assert is_out is False


async def test_should_handoff_false_without_rule():
    conn = FakeConn(fetchrow_result=None)
    result = await should_handoff(conn, {"id": "bot-1"}, "hola", {"id": "conv-1"})
    assert result is False


async def test_should_handoff_on_keyword_match():
    conn = FakeConn(fetchrow_result={"keywords": ["urgente"], "max_bot_attempts": 3})
    result = await should_handoff(
        conn, {"id": "bot-1"}, "Necesito hablar con alguien urgente", {"id": "conv-1"}
    )
    assert result is True


async def test_should_handoff_on_repeated_failed_replies_without_keyword():
    # conversations.failed_reply_count (migración 0012) reemplazó el escaneo de
    # mensajes crudos: antes una racha de fallas quedaba pegada para siempre en el
    # historial y ni reactivar la conversación la rompía.
    rule = {"keywords": [], "max_bot_attempts": 2}
    conn = FakeConn(fetchrow_result=rule)
    result = await should_handoff(conn, {"id": "bot-1"}, "consulta normal sobre precios", {"id": "conv-1", "failed_reply_count": 2})
    assert result is True


async def test_should_handoff_false_when_failed_reply_count_below_threshold():
    rule = {"keywords": [], "max_bot_attempts": 2}
    conn = FakeConn(fetchrow_result=rule)
    result = await should_handoff(conn, {"id": "bot-1"}, "consulta normal sobre precios", {"id": "conv-1", "failed_reply_count": 0})
    assert result is False
