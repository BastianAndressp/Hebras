from __future__ import annotations

from .config import settings
from .db import pool

DEFAULT_COMPANY_ID = "11111111-1111-1111-1111-111111111111"
DEFAULT_USER_ID = "22222222-2222-2222-2222-222222222222"
DEFAULT_BOT_ID = "33333333-3333-3333-3333-333333333333"
DEFAULT_HANDOFF_RULE_ID = "44444444-4444-4444-4444-444444444444"
DEFAULT_KNOWLEDGE_BASE_ID = "55555555-5555-5555-5555-555555555555"


async def bootstrap_demo_data() -> None:
    """Siembra una empresa/bot de ejemplo con UUIDs fijos, sobrescribiéndolos en cada
    arranque. Solo debe correr con DEMO_MODE=true (ver main.py); el esquema en sí vive
    exclusivamente en supabase/migrations/*.sql, no aquí."""
    phone_id = settings.whatsapp_phone_number_id or "100000000000000"
    async with pool().acquire() as conn:
        await conn.execute(
            "delete from audit_logs where company_id = $1 and action = 'system.bootstrap'",
            DEFAULT_COMPANY_ID,
        )

        await conn.execute(
            """
            insert into companies(id, name)
            values($1, 'Mi Empresa')
            on conflict (id) do update set name = excluded.name
            """,
            DEFAULT_COMPANY_ID,
        )

        await conn.execute(
            """
            insert into memberships(id, company_id, user_id, role)
            values(gen_random_uuid(), $1, $2, 'owner')
            on conflict (company_id, user_id) do update set role = excluded.role
            """,
            DEFAULT_COMPANY_ID,
            DEFAULT_USER_ID,
        )

        await conn.execute(
            """
            insert into plans(slug, name, monthly_message_limit, price_amount, currency, is_active)
            values
              ('starter', 'Starter', 300, 9990, 'CLP', true),
              ('pro', 'Pro', 1000, 19990, 'CLP', true),
              ('business', 'Business', 3000, 39990, 'CLP', true)
            on conflict (slug) do update
              set name = excluded.name,
                  monthly_message_limit = excluded.monthly_message_limit,
                  price_amount = excluded.price_amount,
                  currency = excluded.currency,
                  is_active = excluded.is_active
            """
        )

        starter_plan = await conn.fetchrow("select id from plans where slug='starter' limit 1")
        if starter_plan:
            await conn.execute(
                """
                insert into subscriptions(company_id, plan_id, status, current_period_start, current_period_end)
                values($1, $2, 'active', date_trunc('month', now())::date, (date_trunc('month', now()) + interval '1 month')::date)
                on conflict (company_id) do update
                  set plan_id = excluded.plan_id,
                      status = excluded.status,
                      updated_at = now()
                """,
                DEFAULT_COMPANY_ID,
                starter_plan["id"],
            )

        await conn.execute(
            """
            insert into bots(id, company_id, name, phone_number_id, system_prompt, model, fallback_model, temperature, max_tokens, monthly_message_limit, status)
            values($1, $2, 'Asistente de WhatsApp', $3, 'Eres un asistente útil, amable y profesional. Responde en español.', 'deepseek/deepseek-chat', null, 0.4, 400, 300, 'active')
            on conflict (id) do update
              set name = excluded.name,
                  phone_number_id = coalesce(nullif($3, ''), bots.phone_number_id),
                  system_prompt = excluded.system_prompt,
                  model = excluded.model,
                  fallback_model = excluded.fallback_model,
                  temperature = excluded.temperature,
                  max_tokens = excluded.max_tokens,
                  monthly_message_limit = excluded.monthly_message_limit,
                  status = excluded.status,
                  updated_at = now()
            """,
            DEFAULT_BOT_ID,
            DEFAULT_COMPANY_ID,
            phone_id,
        )

        await conn.execute(
            """
            insert into handoff_rules(id, company_id, bot_id, keywords, max_bot_attempts, notification_email)
            values($1, $2, $3, array['humano', 'asesor', 'soporte'], 2, null)
            on conflict (bot_id) do update
              set keywords = excluded.keywords,
                  max_bot_attempts = excluded.max_bot_attempts,
                  notification_email = excluded.notification_email
            """,
            DEFAULT_HANDOFF_RULE_ID,
            DEFAULT_COMPANY_ID,
            DEFAULT_BOT_ID,
        )

        await conn.execute(
            """
            insert into knowledge_bases(id, company_id, bot_id, name)
            values($1, $2, $3, 'Base de conocimiento')
            on conflict (bot_id) do update set name = excluded.name, updated_at = now()
            """,
            DEFAULT_KNOWLEDGE_BASE_ID,
            DEFAULT_COMPANY_ID,
            DEFAULT_BOT_ID,
        )
