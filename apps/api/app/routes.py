import json
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from .auth import Principal, require_owner, require_principal, require_write_access
from .config import settings
from .db import pool, tenant_conn

from .schemas import (
    ApiKeysResponse,
    ApiKeysUpdate,
    AuditLogResponse,
    BillingOverviewResponse,
    BotCreate,
    BotResponse,
    BotUpdate,
    ConversationResponse,
    ConversationStatusUpdate,
    ManualMessageCreate,
    HandoffRuleUpdate,
    NotificationResponse,
    PlanResponse,
    SettingsResponse,
    SettingsUpdate,
    SubscriptionUpdate,
)
from .crypto import decrypt_secret, encrypt_secret
from .services import enforce_whatsapp_trial_claim, get_tenant_api_keys, notify_platform_admin, save_message, send_whatsapp

router = APIRouter(prefix="/v1", tags=["dashboard"])


async def get_bot(conn, company_id: str, bot_id: str | None = None):
    """Resuelve el bot objetivo. Si se pasa bot_id, debe pertenecer a la empresa.
    Si no, cae al primero creado (compatibilidad con empresas de un solo bot)."""
    if bot_id:
        bot = await conn.fetchrow("select * from bots where id=$1 and company_id=$2", bot_id, company_id)
    else:
        bot = await conn.fetchrow("select * from bots where company_id=$1 order by created_at limit 1", company_id)
    if not bot:
        raise HTTPException(404, "No bot configured")
    return bot


@router.get("/bots", response_model=list[BotResponse])
async def list_bots(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        rows = await conn.fetch("select * from bots where company_id=$1 order by created_at asc", principal.company_id)
    return [dict(row) for row in rows]


@router.post("/bots", response_model=BotResponse, status_code=201)
async def create_bot(payload: BotCreate, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        try:
            bot = await conn.fetchrow(
                """insert into bots(company_id, name, phone_number_id, system_prompt)
                   values($1,$2,$3,$4) returning *""",
                principal.company_id, payload.name, payload.phone_number_id, payload.system_prompt,
            )
        except Exception as exc:
            raise HTTPException(400, "Ese número de WhatsApp (phone_number_id) ya está en uso") from exc
        await conn.execute(
            "insert into knowledge_bases(company_id, bot_id, name) values($1,$2,'Base de conocimiento')",
            principal.company_id, bot["id"],
        )
        await conn.execute("insert into audit_logs(company_id, actor_id, action) values($1,$2,'bot.created')", principal.company_id, principal.user_id)
    async with pool().acquire() as elevated_conn:
        await enforce_whatsapp_trial_claim(elevated_conn, principal.company_id, bot["phone_number_id"])
    return dict(bot)


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        total = await conn.fetchval("select count(*) from bots where company_id=$1", principal.company_id)
        if total <= 1:
            raise HTTPException(400, "No puedes eliminar el único bot de la empresa")
        result = await conn.execute("delete from bots where id=$1 and company_id=$2", bot_id, principal.company_id)
        if result.endswith(" 0"):
            raise HTTPException(404, "Bot not found")
        await conn.execute("insert into audit_logs(company_id, actor_id, action) values($1,$2,'bot.deleted')", principal.company_id, principal.user_id)
    return {"ok": True}


@router.get("/bot", response_model=BotResponse)
async def read_bot(bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
    return dict(bot)



@router.put("/bot", response_model=BotResponse)
async def update_bot(payload: BotUpdate, bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        target = await get_bot(conn, principal.company_id, bot_id)
        bot = await conn.fetchrow(
            """update bots set name=$1, system_prompt=$2, model=$3, fallback_model=$4, temperature=$5, max_tokens=$6,
               phone_number_id=coalesce($7, phone_number_id), updated_at=now()
               where id=$8 and company_id=$9 returning *""", payload.name, payload.system_prompt, payload.model,
            payload.fallback_model, payload.temperature, payload.max_tokens, payload.phone_number_id,
            target["id"], principal.company_id)
        await conn.execute("insert into audit_logs(company_id, actor_id, action) values($1,$2,'bot.updated')", principal.company_id, principal.user_id)
    async with pool().acquire() as elevated_conn:
        await enforce_whatsapp_trial_claim(elevated_conn, principal.company_id, bot["phone_number_id"])
    return dict(bot)



@router.get("/handoff-rule")
async def read_handoff_rule(bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        rule = await conn.fetchrow("select keywords, max_bot_attempts, notification_email, ai_handoff_phrase from handoff_rules where bot_id=$1", bot["id"])
    return dict(rule) if rule else {"keywords": [], "max_bot_attempts": 2, "notification_email": None, "ai_handoff_phrase": None}


@router.put("/handoff-rule")
async def update_handoff_rule(payload: HandoffRuleUpdate, bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        rule = await conn.fetchrow(
            """insert into handoff_rules(company_id, bot_id, keywords, max_bot_attempts, notification_email, ai_handoff_phrase)
               values($1,$2,$3,$4,$5,$6) on conflict(bot_id) do update set keywords=excluded.keywords,
               max_bot_attempts=excluded.max_bot_attempts, notification_email=excluded.notification_email,
               ai_handoff_phrase=excluded.ai_handoff_phrase returning *""",
            principal.company_id, bot["id"], payload.keywords, payload.max_bot_attempts, payload.notification_email, payload.ai_handoff_phrase)
    return dict(rule)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        conversations = await conn.fetch("select * from conversations where company_id=$1 order by last_message_at desc limit 100", principal.company_id)
        result = []
        for row in conversations:
            messages = await conn.fetch("select direction, content, created_at from messages where conversation_id=$1 order by created_at asc limit 50", row["id"])
            result.append({**dict(row), "messages": [dict(m) for m in messages]})
    return result


@router.patch("/conversations/{conversation_id}/status")
async def update_conversation_status(conversation_id: str, payload: ConversationStatusUpdate, principal: Principal = Depends(require_principal)):
    require_write_access(principal)
    async with tenant_conn(principal.company_id) as conn:
        conv = await conn.fetchrow(
            "update conversations set status=$1, last_message_at=now() where id=$2 and company_id=$3 returning *",
            payload.status, conversation_id, principal.company_id
        )
        if not conv:
            raise HTTPException(404, "Conversation not found")
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1,$2,$3)",
            principal.company_id, principal.user_id, f"conversation.status_updated_to_{payload.status}"
        )
    return dict(conv)


@router.post("/conversations/{conversation_id}/messages")
async def send_manual_message(conversation_id: str, payload: ManualMessageCreate, principal: Principal = Depends(require_principal)):
    require_write_access(principal)
    async with tenant_conn(principal.company_id) as conn:
        conv = await conn.fetchrow("select * from conversations where id=$1 and company_id=$2", conversation_id, principal.company_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")
        bot = await conn.fetchrow("select * from bots where id=$1", conv["bot_id"])
        if not bot:
            raise HTTPException(404, "Bot not found for conversation")
        api_keys = await get_tenant_api_keys(conn, principal.company_id)

    # La llamada a Meta se hace fuera de la transacción de DB para no mantener
    # una conexión/lock abierto durante un round-trip de red externo.
    wa_token = api_keys.get("whatsapp_access_token")
    await send_whatsapp(bot["phone_number_id"], conv["contact_phone"], payload.content, custom_access_token=wa_token)

    async with tenant_conn(principal.company_id) as conn:
        msg = await save_message(conn, principal.company_id, conv["id"], "outbound", payload.content)
        await conn.execute("update conversations set last_message_at=now() where id=$1", conv["id"])
    return dict(msg)



@router.get("/metrics")
async def metrics(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        row = await conn.fetchrow("""select
          (select count(*) from conversations where company_id=$1 and status='closed') as resolved,
          (select count(*) from conversations where company_id=$1) as total,
          (select count(*) from conversations where company_id=$1 and status='handoff') as handoffs,
          (select coalesce(sum(estimated_cost_usd),0) from messages where company_id=$1) as cost""", principal.company_id)
    total = int(row["total"] or 0)
    return {"conversations": total, "handoffs": int(row["handoffs"] or 0), "estimated_cost_usd": float(row["cost"]),
            "resolution_rate": round((int(row["resolved"] or 0) / total) * 100, 1) if total else 0}


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        logs = await conn.fetch(
            """select id, actor_id, action, created_at
                 from audit_logs
                where company_id = $1
                order by created_at desc
                limit 100""",
            principal.company_id,
        )
    return [dict(row) for row in logs]


@router.get("/billing", response_model=BillingOverviewResponse)
async def read_billing(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        plans = await conn.fetch("select * from plans where is_active = true order by monthly_message_limit asc")
        # OJO: sin filtro de status — una suscripción 'trialing' es una suscripción real
        # y tiene que encontrarse aquí. Filtrar por status='active' era el bug: una
        # cuenta en trial "no se encontraba", caía al fallback de abajo, y esa inserción
        # colisionaba por unique(company_id) contra la fila real y la pisaba a 'active'
        # con el plan Starter cada vez que el dueño abría el dashboard.
        subscription = await conn.fetchrow(
            """select s.id, s.status, s.trial_ends_at, s.current_period_start, s.current_period_end,
                      p.id as plan_id, p.slug, p.name, p.monthly_message_limit, p.price_amount, p.currency, p.is_active
                 from subscriptions s
                 join plans p on p.id = s.plan_id
                where s.company_id = $1""",
            principal.company_id,
        )
        if not subscription:
            # Solo empresas sin NINGUNA fila de suscripción (caso raro: el plan Pro no
            # existía todavía al momento del signup). "do nothing" en vez de
            # "do update ... status='active'": si dos requests concurrentes caen acá,
            # el segundo no debe pisar lo que el primero ya creó.
            starter_plan = await conn.fetchrow("select * from plans where slug='starter' and is_active = true limit 1")
            if starter_plan:
                await conn.execute(
                    """insert into subscriptions(company_id, plan_id, status, current_period_start, current_period_end)
                       values($1,$2,'active', date_trunc('month', now())::date, (date_trunc('month', now()) + interval '1 month')::date)
                       on conflict(company_id) do nothing""",
                    principal.company_id, starter_plan["id"],
                )
                subscription = await conn.fetchrow(
                    """select s.id, s.status, s.trial_ends_at, s.current_period_start, s.current_period_end,
                              p.id as plan_id, p.slug, p.name, p.monthly_message_limit, p.price_amount, p.currency, p.is_active
                         from subscriptions s
                         join plans p on p.id = s.plan_id
                        where s.company_id = $1""",
                    principal.company_id,
                )
        usage_row = await conn.fetchrow(
            """select coalesce(messages_count, 0) as messages_count, coalesce(cost_usd, 0) as cost_usd
                 from usage
                where company_id = $1 and period_start = date_trunc('month', now())::date""",
            principal.company_id,
        )
        total_conversations = await conn.fetchval("select count(*) from conversations where company_id=$1", principal.company_id)

    subscription_payload = None
    if subscription:
        effective_status = subscription["status"]
        trial_ends_at = subscription["trial_ends_at"]
        days_remaining = None
        if effective_status == "trialing" and trial_ends_at:
            remaining = trial_ends_at - datetime.now(timezone.utc)
            if remaining.total_seconds() <= 0:
                effective_status = "trial_expired"
                days_remaining = 0
            else:
                days_remaining = max(1, remaining.days + (1 if remaining.seconds > 0 else 0))
        subscription_payload = {
            "id": subscription["id"],
            "status": effective_status,
            "trial_ends_at": trial_ends_at,
            "days_remaining": days_remaining,
            "current_period_start": subscription["current_period_start"],
            "current_period_end": subscription["current_period_end"],
            "plan": {
                "id": subscription["plan_id"],
                "slug": subscription["slug"],
                "name": subscription["name"],
                "monthly_message_limit": subscription["monthly_message_limit"],
                "price_amount": float(subscription["price_amount"]),
                "currency": subscription["currency"],
                "is_active": subscription["is_active"],
            },
        }
    return {
        "subscription": subscription_payload,
        "plans": [
            {
                "id": row["id"],
                "slug": row["slug"],
                "name": row["name"],
                "monthly_message_limit": row["monthly_message_limit"],
                "price_amount": float(row["price_amount"]),
                "currency": row["currency"],
                "is_active": row["is_active"],
            }
            for row in plans
        ],
        "monthly_message_limit": subscription_payload["plan"]["monthly_message_limit"] if subscription_payload else 0,
        "messages_used": int(usage_row["messages_count"] or 0) if usage_row else 0,
        "estimated_cost_usd": float(usage_row["cost_usd"] or 0) if usage_row else 0,
        "total_conversations": int(total_conversations or 0),
    }


@router.post("/billing/request-upgrade")
async def request_upgrade(payload: SubscriptionUpdate, principal: Principal = Depends(require_principal)):
    """Sin pasarela de pago todavía: esto NO activa el plan (antes PUT /v1/billing sí lo
    hacía al instante, gratis, para cualquier dueño — un agujero real con precios
    reales). Solo registra la solicitud y avisa al operador de la plataforma para
    coordinar el pago manual y activarlo desde /v1/admin/subscriptions/{id}/activate."""
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        plan = await conn.fetchrow("select * from plans where id=$1 and is_active = true", payload.plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        company = await conn.fetchrow("select name from companies where id=$1", principal.company_id)
        price = f"{plan['currency']} {int(plan['price_amount'])}"
        await conn.execute(
            "insert into notifications(company_id, title, message, severity) values($1,$2,$3,'info')",
            principal.company_id,
            "Solicitud de plan enviada",
            f"Pediste cambiar al plan {plan['name']} ({price}/mes). Te contactaremos para coordinar el pago y activarlo.",
        )
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1,$2,'billing.upgrade_requested')",
            principal.company_id, principal.user_id,
        )
    await notify_platform_admin(
        f"Solicitud de upgrade: {company['name'] if company else principal.company_id}",
        f"Empresa: {company['name'] if company else principal.company_id} ({principal.company_id})\n"
        f"Plan solicitado: {plan['name']} ({price}/mes)\n"
        f"Solicitado por user_id: {principal.user_id}\n\n"
        f"Activar con: POST /v1/admin/subscriptions/{principal.company_id}/activate "
        f'{{"plan_id": "{plan["id"]}"}}',
    )
    return {"message": f"Solicitud enviada. Te contactaremos para activar el plan {plan['name']}."}


@router.get("/settings", response_model=SettingsResponse)
async def read_settings(bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        setting = await conn.fetchrow("select * from settings where bot_id=$1", bot["id"])
        if not setting:
            setting = await conn.fetchrow(
                """insert into settings(company_id, bot_id) values($1,$2)
                   on conflict(bot_id) do update set updated_at=now() returning *""",
                principal.company_id, bot["id"]
            )
    res = dict(setting)
    if isinstance(res.get("business_hours"), str):
        res["business_hours"] = json.loads(res["business_hours"])
    return res


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        setting = await conn.fetchrow(
            """insert into settings(company_id, bot_id, business_hours_enabled, business_hours, out_of_hours_message, monthly_spending_limit_usd, default_language)
               values($1,$2,$3,$4::jsonb,$5,$6,$7)
               on conflict(bot_id) do update set
                 business_hours_enabled=excluded.business_hours_enabled,
                 business_hours=excluded.business_hours,
                 out_of_hours_message=excluded.out_of_hours_message,
                 monthly_spending_limit_usd=excluded.monthly_spending_limit_usd,
                 default_language=excluded.default_language,
                 updated_at=now()
               returning *""",
            principal.company_id, bot["id"], payload.business_hours_enabled,
            json.dumps(payload.business_hours), payload.out_of_hours_message,
            payload.monthly_spending_limit_usd, payload.default_language
        )
        await conn.execute("insert into audit_logs(company_id, actor_id, action) values($1,$2,'settings.updated')", principal.company_id, principal.user_id)
    res = dict(setting)
    if isinstance(res.get("business_hours"), str):
        res["business_hours"] = json.loads(res["business_hours"])
    return res



@router.get("/api-keys", response_model=ApiKeysResponse)
async def read_api_keys(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        row = await conn.fetchrow("select whatsapp_access_token, whatsapp_app_secret, openrouter_api_key from api_keys where company_id=$1", principal.company_id)
    return {
        "has_whatsapp_access_token": bool(row and row["whatsapp_access_token"]),
        "has_whatsapp_app_secret": bool(row and row["whatsapp_app_secret"]),
        "has_openrouter_api_key": bool(row and row["openrouter_api_key"]),
    }


@router.get("/webhook-info")
async def read_webhook_info(principal: Principal = Depends(require_principal)):
    """Datos que el dueño necesita pegar en Meta for Developers al configurar SU propio
    webhook: la ruta (se combina con el dominio público en el frontend, ya que el backend
    no conoce el dominio con el que Meta le habla) y un verify token propio de esta
    empresa (no uno global de la plataforma -- cada empresa trae su propia app de Meta).
    Se autogenera la primera vez que se pide, para que el dueño no tenga que inventar ni
    escribir nada."""
    async with tenant_conn(principal.company_id) as conn:
        row = await conn.fetchrow("select whatsapp_verify_token from api_keys where company_id=$1", principal.company_id)
        token = decrypt_secret(row["whatsapp_verify_token"]) if row else None
        if not token:
            token = secrets.token_urlsafe(24)
            await conn.execute(
                """insert into api_keys(company_id, whatsapp_verify_token) values($1,$2)
                   on conflict(company_id) do update set whatsapp_verify_token=excluded.whatsapp_verify_token""",
                principal.company_id, encrypt_secret(token),
            )
    return {
        "webhook_path": "/webhooks/whatsapp",
        "verify_token": token,
    }


@router.put("/api-keys", response_model=ApiKeysResponse)
async def update_api_keys(payload: ApiKeysUpdate, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        row = await conn.fetchrow(
            """insert into api_keys(company_id, whatsapp_access_token, whatsapp_app_secret, openrouter_api_key)
               values($1,$2,$3,$4)
               on conflict(company_id) do update set
                 whatsapp_access_token=coalesce(excluded.whatsapp_access_token, api_keys.whatsapp_access_token),
                 whatsapp_app_secret=coalesce(excluded.whatsapp_app_secret, api_keys.whatsapp_app_secret),
                 openrouter_api_key=coalesce(excluded.openrouter_api_key, api_keys.openrouter_api_key),
                 updated_at=now()
               returning *""",
            principal.company_id,
            encrypt_secret(payload.whatsapp_access_token),
            encrypt_secret(payload.whatsapp_app_secret),
            encrypt_secret(payload.openrouter_api_key),
        )
        await conn.execute("insert into audit_logs(company_id, actor_id, action) values($1,$2,'api_keys.updated')", principal.company_id, principal.user_id)
    return {
        "has_whatsapp_access_token": bool(row and row["whatsapp_access_token"]),
        "has_whatsapp_app_secret": bool(row and row["whatsapp_app_secret"]),
        "has_openrouter_api_key": bool(row and row["openrouter_api_key"]),
    }


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        rows = await conn.fetch("select id, title, message, severity, is_read, created_at from notifications where company_id=$1 order by created_at desc limit 50", principal.company_id)
    return [dict(r) for r in rows]
