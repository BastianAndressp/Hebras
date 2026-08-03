"""Endpoints de administración de la plataforma (no de un tenant): activar manualmente
una suscripción pagada mientras no hay pasarela de pago integrada. Protegidos por un
token compartido (PLATFORM_ADMIN_TOKEN), no por el JWT de un Principal — quien llama
esto es el operador de Hebras, no el dueño de una empresa cliente."""
import hmac
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .db import pool

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _require_admin_token(x_admin_token: str | None) -> None:
    expected = (settings.platform_admin_token or "").strip()
    if not expected:
        raise HTTPException(503, "Administración no configurada (falta PLATFORM_ADMIN_TOKEN)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "Token de administración inválido")


class ActivateSubscriptionRequest(BaseModel):
    plan_id: str
    period_days: int = Field(default=30, ge=1, le=366)


@router.post("/subscriptions/{company_id}/activate")
async def activate_subscription(
    company_id: str,
    payload: ActivateSubscriptionRequest,
    x_admin_token: str | None = Header(default=None),
):
    _require_admin_token(x_admin_token)
    async with pool().acquire() as conn:
        plan = await conn.fetchrow("select * from plans where id=$1 and is_active=true", payload.plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        company = await conn.fetchrow("select id, name from companies where id=$1", company_id)
        if not company:
            raise HTTPException(404, "Company not found")

        period_start = date.today()
        period_end = period_start + timedelta(days=payload.period_days)
        subscription = await conn.fetchrow(
            """insert into subscriptions(company_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
               values($1, $2, 'active', null, $3, $4)
               on conflict(company_id) do update set
                 plan_id = excluded.plan_id,
                 status = 'active',
                 trial_ends_at = null,
                 current_period_start = excluded.current_period_start,
                 current_period_end = excluded.current_period_end,
                 updated_at = now()
               returning *""",
            company_id, payload.plan_id, period_start, period_end,
        )
        await conn.execute(
            "insert into notifications(company_id, title, message, severity) values($1,'Plan activado',$2,'info')",
            company_id, f"Tu plan {plan['name']} fue activado. El bot vuelve a responder con normalidad.",
        )
        # actor_id null: quien activa esto es el operador de la plataforma via token
        # compartido, no un usuario con fila propia en app_users/memberships.
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1, null, 'billing.activated_by_admin')",
            company_id,
        )
    log.info("Subscription activated by admin: company_id=%s plan=%s until=%s", company_id, plan["slug"], period_end)
    return {
        "ok": True,
        "company_id": company_id,
        "company_name": company["name"],
        "plan": plan["slug"],
        "status": subscription["status"],
        "current_period_end": subscription["current_period_end"],
    }
