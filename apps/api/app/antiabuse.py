"""Anti-abuso BLANDO para el registro: nunca bloquea a nadie de forma permanente, solo
frena la creación masiva de cuentas desde una misma conexión y marca cuentas
sospechosas para revisión manual. La barrera dura de verdad contra reciclar pruebas
gratuitas es el número de WhatsApp (ver services.py::enforce_whatsapp_trial_claim) — la
IP es una señal débil por el CGNAT de los ISP móviles chilenos, así que aquí se es
deliberadamente tolerante."""

DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "guerrillamail.info",
    "yopmail.com", "temp-mail.org", "tempmail.com", "throwawaymail.com",
    "trashmail.com", "fakeinbox.com", "getnada.com", "dispostable.com",
    "sharklasers.com", "maildrop.cc", "mintemail.com", "mohmal.com", "moakt.com",
    "tempinbox.com", "discard.email", "spam4.me", "mailnesia.com", "33mail.com",
}


def is_disposable_email(email: str) -> bool:
    parts = email.strip().lower().rsplit("@", 1)
    if len(parts) != 2:
        return False
    return parts[1] in DISPOSABLE_EMAIL_DOMAINS


async def count_recent_trials_for_ip(conn, ip_hash: str) -> int:
    """Empresas nuevas creadas desde esta IP (hasheada) en las últimas 24 h. Solo cuenta
    signup_events con company_id (una cuenta realmente creada), no reenvíos de código."""
    return await conn.fetchval(
        "select count(*) from signup_events where ip_hash=$1 and company_id is not null and created_at > now() - interval '1 day'",
        ip_hash,
    ) or 0


async def total_trials_for_ip(conn, ip_hash: str) -> int:
    """Total histórico de cuentas creadas desde esta IP, para decidir si marcar (flagged)
    la cuenta para revisión manual — nunca para bloquearla."""
    return await conn.fetchval(
        "select count(*) from signup_events where ip_hash=$1 and company_id is not null",
        ip_hash,
    ) or 0
