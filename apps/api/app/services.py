import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx
from .config import settings
from .crypto import decrypt_secret
from .knowledge_utils import chunk_score, chunk_text, generate_embedding


HANDOFF_TERMS = {"humano", "persona", "agente", "asesor", "reclamo", "queja"}

# Antes, un bot recién creado en el signup recibía un phone_number_id FALSO generado al
# azar (f"100{random...}"), indistinguible de un número real conectado de verdad — eso
# rompía cualquier lógica de "este número ya usó una prueba" (Etapa 5) y podía colisionar
# con otro número al azar sin manejo de error. Ahora el placeholder es explícito y
# reconocible con este helper en vez de parecer un número real.
PLACEHOLDER_PHONE_PREFIX = "pending-"


def is_placeholder_number(phone_number_id: str | None) -> bool:
    return not phone_number_id or phone_number_id.startswith(PLACEHOLDER_PHONE_PREFIX)


def get_business_hours(setting) -> dict:
    """settings.business_hours como dict, tolerando que la conexión usada no tenga
    registrado el codec de jsonb (ver db.py::_init_connection, solo se registra en los
    pools de app.db.connect() -- una conexión de test u otro script que abra su propia
    conexión sin pasar por ahí recibiría la columna como texto crudo, no como dict)."""
    if not setting:
        return {}
    bh = setting["business_hours"]
    if isinstance(bh, str):
        try:
            bh = json.loads(bh)
        except (TypeError, ValueError):
            return {}
    return bh if isinstance(bh, dict) else {}


def get_local_now(setting) -> datetime:
    """Hora actual en el timezone configurado del bot (settings.business_hours.timezone).
    Antes, check_business_hours comparaba datetime.now(timezone.utc) directo contra el
    horario configurado sin aplicar nunca el timezone guardado -- silenciosamente
    trataba todo como UTC aunque el bot dijera "America/Santiago". Toda lógica que
    necesite "ahora", "qué día es", o validar un horario de cita debe pasar por acá."""
    tz_name = get_business_hours(setting).get("timezone") or "UTC"
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now(ZoneInfo("UTC"))


DAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


async def check_business_hours(conn, bot_id: str) -> tuple[bool, str]:
    """Retorna (is_out_of_hours, out_of_hours_message)."""
    setting = await conn.fetchrow("select * from settings where bot_id=$1", bot_id)
    if not setting or not setting["business_hours_enabled"]:
        return False, ""

    bh = get_business_hours(setting)
    if "schedule" not in bh:
        return False, ""

    now = get_local_now(setting)
    day_map = DAY_MAP
    day_key = day_map.get(now.weekday())
    day_config = bh.get("schedule", {}).get(day_key, {})
    
    if not day_config.get("active", True):
        return True, setting.get("out_of_hours_message", "Estamos fuera de horario.")
        
    start_str = day_config.get("start", "09:00")
    end_str = day_config.get("end", "18:00")
    current_time_str = now.strftime("%H:%M")
    
    if not (start_str <= current_time_str <= end_str):
        return True, setting.get("out_of_hours_message", "Estamos fuera de horario.")
        
    return False, ""


async def load_bot(conn, phone_number_id: str):
    """Resuelve el bot dueño de este número. Nunca cae a 'cualquier bot activo':
    un phone_number_id desconocido debe descartarse, no enrutarse a otra empresa."""
    return await conn.fetchrow("select * from bots where phone_number_id=$1 and status='active'", phone_number_id)



async def get_or_create_conversation(conn, bot_id: str, contact_phone: str):
    return await conn.fetchrow(
        """insert into conversations (company_id, bot_id, contact_phone) values (
             (select company_id from bots where id=$1), $1, $2)
           on conflict (bot_id, contact_phone) do update set last_message_at=now()
           returning *""", bot_id, contact_phone)


async def should_handoff(conn, bot, text: str, conversation) -> bool:
    rule = await conn.fetchrow("select * from handoff_rules where bot_id=$1", bot["id"])
    if not rule:
        return False
    keywords = {term.lower() for term in (rule["keywords"] or [])} | HANDOFF_TERMS
    if any(term in text.lower() for term in keywords):
        return True
    # conversations.failed_reply_count cuenta fallas reales consecutivas (worker.py lo
    # incrementa cuando generate_reply/send_whatsapp falla, y lo resetea a 0 apenas el
    # bot responde con éxito o el dueño reactiva la conversación a mano). Antes esto
    # escaneaba el historial crudo buscando "los últimos N mensajes son todos entrantes",
    # lo que quedaba pegado para siempre tras una falla real: el chequeo corre ANTES de
    # intentar responder, así que ni reactivar rompía la racha -- cada mensaje nuevo solo
    # la extendía y volvía a derivar al instante, sin que el bot llegara a reintentar.
    if conversation["failed_reply_count"] >= rule["max_bot_attempts"]:
        return True
    return False



async def save_message(conn, company_id, conversation_id, direction, text, meta_message_id=None, tokens=0, cost=0):
    if meta_message_id:
        return await conn.fetchrow(
            """insert into messages (company_id, conversation_id, direction, content, meta_message_id, token_count, estimated_cost_usd)
               values ($1,$2,$3,$4,$5,$6,$7)
               on conflict (meta_message_id) do update set content=excluded.content
               returning *""",
            company_id, conversation_id, direction, text, meta_message_id, tokens, cost)
    return await conn.fetchrow(
        """insert into messages (company_id, conversation_id, direction, content, meta_message_id, token_count, estimated_cost_usd)
           values ($1,$2,$3,$4,$5,$6,$7) returning *""",
        company_id, conversation_id, direction, text, meta_message_id, tokens, cost)


async def get_tenant_api_keys(conn, company_id: str):
    row = await conn.fetchrow("select whatsapp_access_token, whatsapp_app_secret, openrouter_api_key from api_keys where company_id=$1", company_id)
    if not row:
        return {}
    return {
        "whatsapp_access_token": decrypt_secret(row["whatsapp_access_token"]),
        "whatsapp_app_secret": decrypt_secret(row["whatsapp_app_secret"]),
        "openrouter_api_key": decrypt_secret(row["openrouter_api_key"]),
    }


async def generate_reply(
    bot,
    history: list[dict],
    knowledge_context: str = "",
    custom_api_key: str | None = None,
    tools: list[dict] | None = None,
    tool_executor=None,
    max_tool_rounds: int = 3,
) -> tuple[str, int, float]:
    """tool_executor, si se pasa, es un callable async (name: str, args: dict) -> dict
    que NUNCA debe lanzar excepción: cualquier error de la tool (horario no disponible,
    servicio inexistente, etc.) debe volver como {"error": "..."} para que el modelo lo
    vea como resultado de la tool y responda en lenguaje natural, en vez de romper el
    turno completo del worker."""
    api_key = custom_api_key or settings.openrouter_api_key
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    messages: list[dict] = [{"role": "system", "content": bot["system_prompt"]}]
    if knowledge_context:
        messages.append({"role": "system", "content": f"Base de conocimiento relevante:\n{knowledge_context}"})
    messages.extend(history)

    async def call(model: str):
        body = {
            "model": model,
            "messages": messages,
            "temperature": float(bot["temperature"]),
            "max_tokens": int(bot["max_tokens"]),
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{settings.openrouter_base_url}/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        usage = data.get("usage", {})
        return data["choices"][0]["message"], int(usage.get("total_tokens", 0))

    try:
        message, tokens = await call(bot["model"])
        model = bot["model"]
    except httpx.HTTPError:
        if bot["fallback_model"]:
            message, tokens = await call(bot["fallback_model"])
            model = bot["fallback_model"]
        else:
            raise

    total_tokens = tokens
    rounds = 1
    while message.get("tool_calls") and tool_executor and rounds < max_tool_rounds:
        messages.append(message)
        for tool_call in message["tool_calls"]:
            try:
                args = json.loads(tool_call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await tool_executor(tool_call["function"]["name"], args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result, default=str),
            })
        message, tokens = await call(model)
        total_tokens += tokens
        rounds += 1

    if message.get("tool_calls") and not message.get("content"):
        # Se agotaron las rondas de tools sin que el modelo devolviera texto final --
        # evita mandarle al cliente una respuesta vacía por WhatsApp.
        return "Dame un momento, estoy verificando la disponibilidad.", total_tokens, 0.0
    return (message.get("content") or "").strip(), total_tokens, 0.0


async def send_whatsapp(phone_number_id: str, recipient: str, text: str, custom_access_token: str | None = None, conn = None) -> None:
    access_token = custom_access_token or settings.whatsapp_access_token
    url = f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": text}}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code >= 400:
            import logging
            logging.error("Error al enviar mensaje por WhatsApp Cloud API: %s - %s", response.status_code, response.text)
            if conn:
                try:
                    error_json = response.json()
                    err_msg = error_json.get("error", {}).get("message", response.text)
                    bot = await conn.fetchrow("select company_id from bots where phone_number_id=$1 limit 1", phone_number_id)
                    if bot:
                        await conn.execute(
                            "insert into notifications(company_id, title, message, severity) values($1,$2,$3,'error')",
                            bot["company_id"], "Fallo al enviar WhatsApp", f"Error de Meta API: {err_msg[:200]}"
                        )
                except Exception:
                    pass
        response.raise_for_status()




async def notify_handoff(email: str | None, contact: str, text: str) -> None:
    if not email or not settings.brevo_api_key:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                json={
                    "sender": {"email": settings.email_from, "name": "Hebras"},
                    "to": [{"email": email}],
                    "subject": f"Conversación requiere atención: {contact}",
                    "textContent": f"El cliente {contact} escribió: {text}",
                },
            )
            response.raise_for_status()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("No se pudo notificar la derivación a humano por email a %s", email)


async def notify_platform_admin(subject: str, text: str) -> None:
    """Aviso al operador de la plataforma (no a un tenant) — hoy solo se usa para
    solicitudes de upgrade de plan, mientras no hay pasarela de pago (cobro manual, ver
    admin_router.py). Requiere PLATFORM_ADMIN_EMAIL; sin eso, no hay a quién avisar."""
    if not settings.platform_admin_email or not settings.brevo_api_key:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                json={
                    "sender": {"email": settings.email_from, "name": "Hebras"},
                    "to": [{"email": settings.platform_admin_email}],
                    "subject": subject,
                    "textContent": text,
                },
            )
            response.raise_for_status()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("No se pudo notificar al admin de la plataforma")


async def store_document(conn, company_id: str, knowledge_base_id: str, title: str, content: str, source_type: str = "manual"):
    chunks = chunk_text(content)
    document = await conn.fetchrow(
        """insert into documents(company_id, knowledge_base_id, title, source_type, source_text, status, chunk_count)
           values($1,$2,$3,$4,$5,'ready',$6) returning *""",
        company_id, knowledge_base_id, title, source_type, content, len(chunks),
    )
    for index, chunk in enumerate(chunks):
        emb = await generate_embedding(chunk)
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"
        try:
            await conn.execute(
                """insert into document_chunks(company_id, document_id, chunk_index, content, embedding)
                   values($1,$2,$3,$4,$5::vector)""",
                company_id, document["id"], index, chunk, emb_str,
            )
        except Exception:
            # Fallback si la columna o extensión pgvector no está activa aún en la DB
            await conn.execute(
                """insert into document_chunks(company_id, document_id, chunk_index, content)
                   values($1,$2,$3,$4)""",
                company_id, document["id"], index, chunk,
            )
    return document, chunks


async def fetch_relevant_chunks(conn, bot_id: str, query: str, limit: int = 4) -> list[str]:
    try:
        query_emb = await generate_embedding(query)
        query_emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"
        rows = await conn.fetch(
            """select dc.content, (dc.embedding <=> $2::vector) as dist
                 from document_chunks dc
                 join documents d on d.id = dc.document_id
                 join knowledge_bases kb on kb.id = d.knowledge_base_id
                where kb.bot_id = $1 and d.status = 'ready' and dc.embedding is not null
                  and (dc.embedding <=> $2::vector) < 0.65
                order by dist asc
                limit $3""",
            bot_id, query_emb_str, limit,
        )
        if rows:
            return [row["content"] for row in rows]
    except Exception:
        pass

    # Fallback por puntuación de términos
    rows = await conn.fetch(
        """select dc.content
             from document_chunks dc
             join documents d on d.id = dc.document_id
             join knowledge_bases kb on kb.id = d.knowledge_base_id
            where kb.bot_id = $1 and d.status = 'ready'
            order by dc.created_at desc
            limit 200""",
        bot_id,
    )
    ranked = sorted(
        ((chunk_score(query, row["content"]), row["content"]) for row in rows),
        key=lambda item: item[0],
        reverse=True,
    )
    return [content for score, content in ranked[:limit] if score > 0]


async def build_knowledge_context(conn, bot_id: str, query: str) -> str:
    chunks = await fetch_relevant_chunks(conn, bot_id, query)
    if not chunks:
        return ""
    return "\n\n".join(f"Fragmento relevante {index + 1}: {chunk}" for index, chunk in enumerate(chunks))


async def get_current_usage_count(conn, company_id: str) -> int:
    used = await conn.fetchval(
        "select coalesce(messages_count, 0) from usage where company_id=$1 and period_start=date_trunc('month', now())::date",
        company_id,
    )
    return int(used or 0)


async def resolve_account_state(conn, company_id: str) -> dict:
    """Resuelve el estado real de la cuenta. El vencimiento del trial se deriva al leer
    (status='trialing' + trial_ends_at pasado -> 'trial_expired'): el proyecto no tiene
    ningún cron, así que no hay otro momento en que esto se actualice solo.
    Nunca lanza: sin suscripción, el estado es 'no_subscription' con límite 0 (cuenta
    bloqueada, no un error) — antes esto hacía TypeError y tumbaba al worker."""
    row = await conn.fetchrow(
        """select s.status, s.trial_ends_at, p.monthly_message_limit, p.slug as plan_slug
             from subscriptions s
             join plans p on p.id = s.plan_id
            where s.company_id = $1 and p.is_active = true""",
        company_id,
    )
    if not row:
        return {"status": "no_subscription", "plan_slug": None, "plan_limit": 0, "effective_limit": 0}

    status = row["status"]
    if status == "trialing" and row["trial_ends_at"] and row["trial_ends_at"] < datetime.now(timezone.utc):
        status = "trial_expired"

    plan_limit = int(row["monthly_message_limit"] or 0)
    if status in ("trial_expired", "canceled"):
        effective_limit = 0
    elif status == "trialing":
        effective_limit = min(plan_limit, settings.trial_message_cap)
    else:
        effective_limit = plan_limit

    return {"status": status, "plan_slug": row["plan_slug"], "plan_limit": plan_limit, "effective_limit": effective_limit}


async def get_company_message_limit(conn, company_id: str, bot_limit: int) -> int:
    state = await resolve_account_state(conn, company_id)
    return min(state["effective_limit"], bot_limit)


async def enforce_whatsapp_trial_claim(elevated_conn, company_id: str, phone_number_id: str) -> None:
    """Barrera dura anti-abuso: un número de WhatsApp real solo da una prueba gratuita,
    sin importar cuántas cuentas nuevas se creen. whatsapp_number_claims es una tabla de
    sistema SIN RLS (como webhook_events) porque esta consulta es, por diseño,
    cross-tenant: hay que poder ver si el número ya se usó bajo OTRA empresa. Por eso
    recibe una conexión del pool elevado, nunca una tenant_conn.

    No bloquea la conexión del número en sí — bots.phone_number_id ya es único a nivel
    de base de datos, así que solo una empresa puede tenerlo activo a la vez. Lo que
    hace es cortar el trial de esta empresa si el número ya se gastó en otra."""
    if is_placeholder_number(phone_number_id):
        return

    existing = await elevated_conn.fetchrow(
        "select company_id from whatsapp_number_claims where phone_number_id=$1", phone_number_id
    )
    if existing is None:
        await elevated_conn.execute(
            "insert into whatsapp_number_claims(phone_number_id, company_id, trial_consumed) values($1,$2,true)",
            phone_number_id, company_id,
        )
        return
    if str(existing["company_id"]) == str(company_id):
        return

    # El número ya se usó bajo otra empresa: esta empresa no obtiene ni mantiene un
    # trial con él. No toca cuentas que ya pagan (status distinto de 'trialing').
    await elevated_conn.execute(
        "update subscriptions set status='trial_expired', updated_at=now() where company_id=$1 and status='trialing'",
        company_id,
    )


async def notify_account_blocked(conn, company_id: str, reason: str) -> None:
    """Como mucho un aviso por día por empresa, no uno por cada mensaje bloqueado."""
    existing = await conn.fetchval(
        """select 1 from notifications
            where company_id=$1 and title='Bot pausado por facturación' and created_at > now() - interval '1 day'
            limit 1""",
        company_id,
    )
    if existing:
        return
    await conn.execute(
        "insert into notifications(company_id, title, message, severity) values($1,'Bot pausado por facturación',$2,'warning')",
        company_id, reason,
    )

