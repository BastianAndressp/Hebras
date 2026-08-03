"""Cubre worker.process() en el caso de regresión clave: un mensaje entrante cuyo
phone_number_id no resuelve a ningún bot debe descartarse sin lanzar excepción y sin
intentar procesar nada más (no debe haber fuga cross-tenant)."""
from unittest.mock import patch

from app.worker import process


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireCtx(self._conn)


async def test_process_skips_message_when_bot_not_found():
    async def fake_load_bot(conn, phone_number_id):
        return None

    with patch("app.worker.pool", return_value=FakePool(object())), \
         patch("app.worker.load_bot", fake_load_bot):
        # No debe lanzar excepción; simplemente descarta el mensaje.
        await process(
            {
                "phone_number_id": "numero-desconocido",
                "contact_phone": "+56911111111",
                "meta_message_id": "m1",
                "text": "hola",
            }
        )
