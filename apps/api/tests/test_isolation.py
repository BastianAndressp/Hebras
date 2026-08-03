"""Regresión directa del hallazgo de seguridad: un phone_number_id desconocido nunca
debe enrutarse a un bot de otra empresa. Antes, load_bot caía a 'cualquier bot activo'."""
from app.services import load_bot


class FakeConn:
    def __init__(self, row=None):
        self.row = row
        self.queries: list[tuple[str, tuple]] = []

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        return self.row


async def test_load_bot_returns_none_for_unknown_phone_number_id():
    conn = FakeConn(row=None)
    bot = await load_bot(conn, "phone-number-id-inexistente")
    assert bot is None
    # Una sola query (por phone_number_id); nunca un segundo intento sin filtro.
    assert len(conn.queries) == 1


async def test_load_bot_returns_matching_bot():
    fake_bot = {"id": "bot-1", "phone_number_id": "123", "company_id": "company-1"}
    conn = FakeConn(row=fake_bot)
    bot = await load_bot(conn, "123")
    assert bot == fake_bot
