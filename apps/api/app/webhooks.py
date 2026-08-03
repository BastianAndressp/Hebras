import hashlib
import hmac
import json
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response


from .config import settings
from .db import pool
from .queue import enqueue

router = APIRouter(prefix="/webhooks", tags=["whatsapp"])


PLACEHOLDER_APP_SECRETS = {"change-me", "REEMPLAZAR_CON_APP_SECRET_DE_META"}


def is_app_secret_configured() -> bool:
    app_secret = (settings.whatsapp_app_secret or "").strip("'\"")
    return bool(app_secret) and app_secret not in PLACEHOLDER_APP_SECRETS


def is_valid_signature(raw: bytes, signature: str | None) -> bool:
    """Valida la firma HMAC-SHA256 de Meta. Requiere WHATSAPP_APP_SECRET configurado
    y el header X-Hub-Signature-256 presente; nunca acepta el request por omisión."""
    import logging
    log = logging.getLogger(__name__)
    if not is_app_secret_configured() or not signature:
        return False
    app_secret = (settings.whatsapp_app_secret or "").strip("'\"")
    sig_hash = signature.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(expected, sig_hash)
    if not valid:
        log.error("Signature mismatch! expected=%s..., received=%s...", expected[:16], sig_hash[:16])
    return valid



@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    expected_token = (settings.webhook_verify_token or "").strip("'\"")
    if hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token or "", expected_token):
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(403, "Webhook verification failed")



def inbound_messages(payload: dict):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            for message in value.get("messages", []):
                if message.get("type") == "text":
                    yield {
                        "meta_message_id": message["id"],
                        "phone_number_id": metadata.get("phone_number_id"),
                        "contact_phone": message.get("from"),
                        "text": message.get("text", {}).get("body", "").strip(),
                        "timestamp": message.get("timestamp"),
                    }


@router.post("/whatsapp", status_code=200)
async def receive_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None)):
    import logging
    log = logging.getLogger(__name__)
    raw = await request.body()
    log.info("Received Webhook POST payload: %s", raw.decode("utf-8", errors="replace"))
    if not is_app_secret_configured():
        raise HTTPException(503, "Integración de WhatsApp no configurada (falta WHATSAPP_APP_SECRET)")
    if not is_valid_signature(raw, x_hub_signature_256):
        raise HTTPException(403, "Invalid Meta signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON") from exc

    async with pool().acquire() as conn:
        for message in inbound_messages(payload):
            inserted = await conn.fetchval(
                """insert into webhook_events (meta_message_id, payload) values ($1, $2::jsonb)
                   on conflict (meta_message_id) do nothing returning meta_message_id""",
                message["meta_message_id"], json.dumps(message),
            )
            if inserted:
                await enqueue(message)
    return {"received": True}

