import asyncio
import json
import logging
import sys
from .db import connect, disconnect, pool
from .queue import QUEUE_NAME, redis_client
from .services import (build_knowledge_context, check_business_hours, get_current_usage_count,
                       get_or_create_conversation, get_tenant_api_keys, load_bot, notify_account_blocked, notify_handoff,
                       resolve_account_state, save_message, send_whatsapp, should_handoff, generate_reply)

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
log = logging.getLogger(__name__)



async def process(payload: dict) -> None:
    log.info("Processing message meta_message_id=%s, phone_number_id=%s, contact=%s, text=%s",
             payload.get("meta_message_id"), payload.get("phone_number_id"), payload.get("contact_phone"), payload.get("text"))
    async with pool().acquire() as conn:
        bot = await load_bot(conn, payload["phone_number_id"])
        if not bot:
            log.warning("No active bot found for phone_number_id=%s", payload["phone_number_id"])
            return
        conversation = await get_or_create_conversation(conn, bot["id"], payload["contact_phone"])
        await save_message(conn, bot["company_id"], conversation["id"], "inbound", payload["text"], payload["meta_message_id"])

        api_keys = await get_tenant_api_keys(conn, bot["company_id"])
        wa_token = api_keys.get("whatsapp_access_token")
        or_key = api_keys.get("openrouter_api_key")

        # Chequeo de horario laboral
        is_out_of_hours, out_msg = await check_business_hours(conn, bot["id"])
        if is_out_of_hours and out_msg:
            log.info("Out of business hours, sending automated reply")
            await send_whatsapp(bot["phone_number_id"], payload["contact_phone"], out_msg, custom_access_token=wa_token)
            await save_message(conn, bot["company_id"], conversation["id"], "outbound", out_msg)
            return

        # Bloqueo de cuenta (trial vencido, sin suscripción, o cuota agotada) es un caso
        # DISTINTO de la derivación a humano: antes ambos caían en la misma rama y
        # marcaban status='handoff', dejando la conversación muerta para el bot incluso
        # después de que la empresa pagara o el mes se reiniciara (nadie revertía ese
        # estado). Ahora el bloqueo por facturación nunca toca conversations.status —
        # el bot simplemente deja de responder hasta que la cuenta se desbloquee.
        account_state = await resolve_account_state(conn, bot["company_id"])
        current_usage = await get_current_usage_count(conn, bot["company_id"])
        company_limit = min(account_state["effective_limit"], bot["monthly_message_limit"])

        block_reason = None
        if account_state["status"] == "trial_expired":
            block_reason = "Tu período de prueba de 7 días terminó. Activa un plan para que el bot vuelva a responder."
        elif account_state["status"] in ("no_subscription", "canceled"):
            block_reason = "No tienes una suscripción activa. El bot no está respondiendo."
        elif current_usage >= company_limit:
            block_reason = "Alcanzaste el límite de mensajes de tu plan este mes. El bot volverá a responder el próximo período, o puedes subir de plan."

        if block_reason:
            log.info("Account blocked for company_id=%s (status=%s, usage=%s/%s): %s",
                      bot["company_id"], account_state["status"], current_usage, company_limit, block_reason)
            await notify_account_blocked(conn, bot["company_id"], block_reason)
            return

        if conversation["status"] == "handoff" or await should_handoff(conn, bot, payload["text"], conversation):
            log.info("Triggering handoff for conversation_id=%s", conversation["id"])
            await conn.execute("update conversations set status='handoff', last_message_at=now() where id=$1", conversation["id"])
            email = await conn.fetchval("select notification_email from handoff_rules where bot_id=$1", bot["id"])
            await notify_handoff(email, payload["contact_phone"], payload["text"])
            return

        knowledge_context = await build_knowledge_context(conn, bot["id"], payload["text"])
        history_rows = await conn.fetch("select direction, content from messages where conversation_id=$1 order by created_at desc limit 12", conversation["id"])
    
    recent_history = list(reversed(history_rows))
    if len(recent_history) > 6:
        older = recent_history[:-6]
        summary_snippets = [f"{'Cliente' if m['direction']=='inbound' else 'Bot'}: {m['content'][:60]}" for m in older]
        summary_text = "Resumen de mensajes anteriores: " + " | ".join(summary_snippets)
        messages = [{"role": "system", "content": summary_text}]
        messages.extend([{"role": "assistant" if m["direction"] == "outbound" else "user", "content": m["content"]} for m in recent_history[-6:]])
    else:
        messages = [{"role": "assistant" if m["direction"] == "outbound" else "user", "content": m["content"]} for m in recent_history]

    try:
        log.info("Generating reply via OpenRouter for model=%s...", bot["model"])
        reply, tokens, cost = await generate_reply(bot, messages, knowledge_context=knowledge_context, custom_api_key=or_key)
        log.info("Generated reply: '%s' (%d tokens)", reply, tokens)
        out_phone_id = payload.get("phone_number_id") or bot["phone_number_id"]
        await send_whatsapp(out_phone_id, payload["contact_phone"], reply, custom_access_token=wa_token)
        log.info("Successfully sent WhatsApp reply to %s", payload["contact_phone"])

        async with pool().acquire() as conn:
            await save_message(conn, bot["company_id"], conversation["id"], "outbound", reply, tokens=tokens, cost=cost)
            await conn.execute("insert into usage(company_id, period_start, messages_count, tokens_count, cost_usd) values($1,date_trunc('month',now()),1,$2,$3) on conflict(company_id,period_start) do update set messages_count=usage.messages_count+1,tokens_count=usage.tokens_count+excluded.tokens_count,cost_usd=usage.cost_usd+excluded.cost_usd", bot["company_id"], tokens, cost)

    except Exception:
        log.exception("Message processing failed for meta_message_id=%s", payload.get("meta_message_id"))
        raise


async def listen() -> None:
    """Loop del worker, asumiendo que connect() ya corrió (pools de db.py ya están
    inicializados). Separado de run() para poder correrse como tarea de fondo dentro
    del mismo proceso de la API (ver main.py, RUN_WORKER_IN_PROCESS) sin pisar los
    pools globales que la API ya está usando."""
    log.info("Worker started listening on Redis queue: %s", QUEUE_NAME)
    redis = await redis_client()
    while True:
        item = await redis.brpop(QUEUE_NAME, timeout=5)
        if item:
            _, raw = item
            payload = json.loads(raw)
            log.info("Dequeued message from Redis: %s", payload.get("meta_message_id"))
            try:
                await process(payload)
            except Exception:
                retries = int(payload.get("retries", 0))
                if retries < 3:
                    payload["retries"] = retries + 1
                    await asyncio.sleep(2 ** retries)
                    await redis.lpush(QUEUE_NAME, json.dumps(payload, default=str))
                else:
                    log.exception("Message permanently failed", extra={"message_id": payload.get("meta_message_id")})


async def run() -> None:
    """Punto de entrada para el worker como proceso standalone (docker-compose local,
    o un Background Worker separado en Render)."""
    await connect()
    try:
        await listen()
    finally:
        await disconnect()


if __name__ == "__main__":
    asyncio.run(run())

