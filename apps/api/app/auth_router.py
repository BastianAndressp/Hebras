from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import random
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Request
import httpx
import jwt

from .antiabuse import count_recent_trials_for_ip, is_disposable_email, total_trials_for_ip
from .config import settings
from .crypto import hash_value
from .db import pool
from .net import get_client_ip
from .services import PLACEHOLDER_PHONE_PREFIX
from .schemas import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    SignUpRequest,
    VerifyEmailRequest,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth", tags=["auth"])


def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return hmac_compare(key, new_key)
    except Exception:
        return False


def hmac_compare(val1: bytes, val2: bytes) -> bool:
    import hmac
    return hmac.compare_digest(val1, val2)


def generate_jwt(user_id: str, company_id: str, role: str = "owner", email: str = "") -> str:
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role": role,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


PLACEHOLDER_BREVO_KEYS = {"", "REEMPLAZAR_CON_API_KEY_DE_BREVO", "change-me"}


async def _send_email_via_brevo(to_email: str, subject: str, text_content: str) -> bool:
    """True si Brevo aceptó el request. Nota: Brevo responde 201 apenas encola el
    envío — un remitente (EMAIL_FROM) sin verificar en la cuenta igual lo rechaza
    después de forma asíncrona; eso solo se ve en el panel de Brevo, no en esta
    respuesta. Nunca lanza excepción, solo loguea."""
    brevo_key = (settings.brevo_api_key or "").strip()
    if brevo_key in PLACEHOLDER_BREVO_KEYS:
        log.info("BREVO_API_KEY no configurada: el contenido del correo solo queda en este log.")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": brevo_key, "accept": "application/json"},
                json={
                    "sender": {"email": settings.email_from or "noreply@example.com", "name": "Hebras"},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "textContent": text_content,
                },
            )
            response.raise_for_status()
        log.info("Email aceptado por Brevo para %s (revisa el panel de Brevo si no llega: puede rechazarse "
                  "después si EMAIL_FROM no está verificado)", to_email)
        return True
    except httpx.HTTPStatusError as exc:
        log.error(
            "Brevo rechazó el envío a %s (status=%s): %s. Revisa BREVO_API_KEY y que "
            "EMAIL_FROM sea un remitente verificado en tu cuenta de Brevo.",
            to_email, exc.response.status_code, exc.response.text,
        )
    except Exception as exc:
        log.error("No se pudo enviar email por Brevo a %s: %s", to_email, exc)
    return False


async def send_verification_email(email: str, code: str) -> None:
    subject = f"Código de verificación de tu cuenta: {code}"
    body_text = f"Hola,\n\nTu código de verificación para Hebras es:\n\n{code}\n\nEste código expira en 15 minutos."
    if not await _send_email_via_brevo(email, subject, body_text):
        log.info("CÓDIGO DE VERIFICACIÓN PARA %s: [%s]", email, code)


async def send_password_reset_email(email: str, code: str) -> None:
    subject = "Código para restablecer tu contraseña"
    body_text = (
        f"Hola,\n\nRecibimos una solicitud para restablecer tu contraseña en Hebras.\n\n"
        f"Tu código es:\n\n{code}\n\nSi no fuiste tú, ignora este correo. El código expira en 15 minutos."
    )
    if not await _send_email_via_brevo(email, subject, body_text):
        log.info("CÓDIGO DE RECUPERACIÓN DE CONTRASEÑA PARA %s: [%s]", email, code)


@router.post("/signup")
async def signup(payload: SignUpRequest, request: Request):
    email_clean = payload.email.strip().lower()

    if is_disposable_email(email_clean):
        raise HTTPException(400, "No aceptamos correos de dominios desechables. Usa un correo real para registrarte.")

    client_ip = get_client_ip(request)
    ip_hash = hash_value(client_ip)
    ua_hash = hash_value(request.headers.get("user-agent") or "unknown")

    async with pool().acquire() as conn:
        existing = await conn.fetchrow("select id, is_email_verified from app_users where lower(email)=$1", email_clean)
        if existing:
            if existing["is_email_verified"]:
                raise HTTPException(400, "El correo electrónico ya está registrado e verificado. Por favor inicia sesión.")
            # Si existía pero no estaba verificado, generar nuevo código. No cuenta
            # contra el límite diario de registros por IP: no crea una empresa nueva,
            # solo reenvía el código de una que ya existe.
            code = f"{random.randint(100000, 999999)}"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            await conn.execute(
                "update app_users set verification_code=$1, verification_expires_at=$2, updated_at=now() where id=$3",
                code, expires_at, existing["id"]
            )
            await send_verification_email(email_clean, code)
            return {
                "message": "Registro pendiente de verificación. Te hemos enviado un código a tu correo.",
                "email": email_clean,
                "requires_verification": True,
            }

        # Señal blanda anti-abuso: frena la creación masiva de empresas nuevas desde una
        # misma conexión sin bloquear a nadie de forma permanente (ver antiabuse.py — el
        # tope es generoso a propósito por el CGNAT de los ISP móviles chilenos).
        recent_signups = await count_recent_trials_for_ip(conn, ip_hash)
        if recent_signups >= settings.signup_ip_daily_limit:
            raise HTTPException(
                429,
                "Demasiadas cuentas nuevas creadas hoy desde esta conexión. Intenta de nuevo mañana o contáctanos.",
            )

        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        pw_hash = hash_password(payload.password)

        # Todo el aprovisionamiento (usuario, empresa, membresía, bot, KB, suscripción de
        # prueba) va en una sola transacción: antes no había ninguna, así que un fallo a
        # mitad de camino (ej. el insert del bot) dejaba una empresa/usuario huérfanos.
        async with conn.transaction():
            # Crear usuario
            user_row = await conn.fetchrow(
                """insert into app_users(email, password_hash, company_name, is_email_verified, verification_code, verification_expires_at)
                   values($1, $2, $3, false, $4, $5) returning *""",
                email_clean, pw_hash, payload.company_name, code, expires_at
            )

            # Crear empresa propia
            company_row = await conn.fetchrow(
                "insert into companies(name) values($1) returning id",
                payload.company_name
            )

            # Crear membresía como owner
            await conn.execute(
                "insert into memberships(company_id, user_id, role) values($1, $2, 'owner')",
                company_row["id"], user_row["id"]
            )

            # Prueba gratuita de 7 días en el plan Pro (para mostrar el producto completo,
            # no una versión recortada). Si por algún motivo el plan no existe todavía
            # (entorno recién migrado), la cuenta sigue sin suscripción en vez de romper
            # el registro; get_company_message_limit trata eso como cuenta bloqueada.
            pro_plan = await conn.fetchrow("select id from plans where slug='pro' and is_active = true limit 1")
            if pro_plan:
                trial_ends_at = datetime.now(timezone.utc) + timedelta(days=settings.trial_days)
                await conn.execute(
                    """insert into subscriptions(company_id, plan_id, status, trial_ends_at, current_period_start, current_period_end)
                       values($1, $2, 'trialing', $3, date_trunc('month', now())::date, (date_trunc('month', now()) + interval '1 month')::date)""",
                    company_row["id"], pro_plan["id"], trial_ends_at,
                )

            # Bot inicial: número placeholder explícito, no un número real hasta que el
            # dueño conecte su WhatsApp Business de verdad (ver PUT /v1/bot y Etapa 5).
            bot_row = await conn.fetchrow(
                """insert into bots(company_id, name, phone_number_id, system_prompt)
                   values($1, $2, $3, 'Eres un asistente de atención al cliente amable y profesional. Responde en español.')
                   returning id""",
                company_row["id"],
                f"Bot de {payload.company_name}",
                f"{PLACEHOLDER_PHONE_PREFIX}{uuid4()}",
            )

            # Crear base de conocimiento inicial
            await conn.execute(
                "insert into knowledge_bases(company_id, bot_id, name) values($1, $2, 'Base de conocimiento')",
                company_row["id"], bot_row["id"]
            )

        # signup_events es tabla de sistema sin RLS (igual que webhook_events): registra
        # el hash de IP/user-agent, nunca el dato crudo (es dato personal bajo la Ley
        # 21.719). Si esta misma IP ya acumula varias cuentas históricas, se marca para
        # revisión manual — nunca se bloquea automáticamente.
        prior_trials = await total_trials_for_ip(conn, ip_hash)
        flagged = (prior_trials + 1) >= settings.signup_flag_threshold
        await conn.execute(
            "insert into signup_events(email, ip_hash, user_agent_hash, company_id, flagged) values($1,$2,$3,$4,$5)",
            email_clean, ip_hash, ua_hash, company_row["id"], flagged,
        )

        await send_verification_email(email_clean, code)

        return {
            "message": "Cuenta creada exitosamente. Por favor verifica tu correo electrónico con el código enviado.",
            "email": email_clean,
            "requires_verification": True,
        }


@router.post("/verify-email", response_model=AuthTokenResponse)
async def verify_email(payload: VerifyEmailRequest):
    email_clean = payload.email.strip().lower()
    code_clean = payload.code.strip()

    async with pool().acquire() as conn:
        user = await conn.fetchrow("select * from app_users where lower(email)=$1", email_clean)
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

        if user["is_email_verified"]:
            # Ya verificado, buscar company_id y entregar token
            membership = await conn.fetchrow("select company_id, role from memberships where user_id=$1 limit 1", user["id"])
            cid = str(membership["company_id"]) if membership else str(user["id"])
            role = membership["role"] if membership else "owner"
            token = generate_jwt(str(user["id"]), cid, role, email_clean)
            return AuthTokenResponse(access_token=token, user_id=user["id"], company_id=UUID(cid), role=role)

        if not user["verification_code"] or user["verification_code"] != code_clean:
            raise HTTPException(400, "Código de verificación incorrecto")

        if user["verification_expires_at"] and user["verification_expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "El código de verificación ha expirado. Por favor solicita uno nuevo.")

        # Marcar como verificado
        await conn.execute(
            "update app_users set is_email_verified=true, verification_code=null, updated_at=now() where id=$1",
            user["id"]
        )

        membership = await conn.fetchrow("select company_id, role from memberships where user_id=$1 limit 1", user["id"])
        cid = str(membership["company_id"]) if membership else str(user["id"])
        role = membership["role"] if membership else "owner"

        token = generate_jwt(str(user["id"]), cid, role, email_clean)
        return AuthTokenResponse(access_token=token, user_id=user["id"], company_id=UUID(cid), role=role)


@router.post("/resend-code")
async def resend_code(payload: ResendCodeRequest):
    email_clean = payload.email.strip().lower()
    async with pool().acquire() as conn:
        user = await conn.fetchrow("select * from app_users where lower(email)=$1", email_clean)
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

        if user["is_email_verified"]:
            return {"message": "El correo ya se encuentra verificado. Puedes iniciar sesión."}

        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        await conn.execute(
            "update app_users set verification_code=$1, verification_expires_at=$2, updated_at=now() where id=$3",
            code, expires_at, user["id"]
        )

        await send_verification_email(email_clean, code)
        return {
            "message": "Nuevo código de verificación enviado.",
            "email": email_clean,
        }


@router.post("/login", response_model=AuthTokenResponse)
async def login(payload: LoginRequest):
    email_clean = payload.email.strip().lower()
    async with pool().acquire() as conn:
        user = await conn.fetchrow("select * from app_users where lower(email)=$1", email_clean)
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(401, "Correo o contraseña incorrectos")

        if not user["is_email_verified"]:
            raise HTTPException(
                403,
                detail={
                    "message": "Debes verificar tu correo electrónico antes de ingresar.",
                    "requires_verification": True,
                    "email": email_clean,
                }
            )

        membership = await conn.fetchrow("select company_id, role from memberships where user_id=$1 limit 1", user["id"])
        cid = str(membership["company_id"]) if membership else str(user["id"])
        role = membership["role"] if membership else "owner"

        token = generate_jwt(str(user["id"]), cid, role, email_clean)
        return AuthTokenResponse(access_token=token, user_id=user["id"], company_id=UUID(cid), role=role)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    email_clean = payload.email.strip().lower()
    async with pool().acquire() as conn:
        user = await conn.fetchrow("select id from app_users where lower(email)=$1", email_clean)
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        await conn.execute(
            "update app_users set verification_code=$1, verification_expires_at=$2, updated_at=now() where id=$3",
            code, expires_at, user["id"],
        )
        await send_password_reset_email(email_clean, code)
        return {
            "message": "Te hemos enviado un código para restablecer tu contraseña.",
            "email": email_clean,
        }


@router.post("/reset-password", response_model=AuthTokenResponse)
async def reset_password(payload: ResetPasswordRequest):
    email_clean = payload.email.strip().lower()
    code_clean = payload.code.strip()

    async with pool().acquire() as conn:
        user = await conn.fetchrow("select * from app_users where lower(email)=$1", email_clean)
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

        if not user["verification_code"] or user["verification_code"] != code_clean:
            raise HTTPException(400, "Código incorrecto")

        if user["verification_expires_at"] and user["verification_expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(400, "El código ha expirado. Solicita uno nuevo.")

        new_hash = hash_password(payload.new_password)
        await conn.execute(
            "update app_users set password_hash=$1, verification_code=null, verification_expires_at=null, updated_at=now() where id=$2",
            new_hash, user["id"],
        )

        membership = await conn.fetchrow("select company_id, role from memberships where user_id=$1 limit 1", user["id"])
        cid = str(membership["company_id"]) if membership else str(user["id"])
        role = membership["role"] if membership else "owner"

        token = generate_jwt(str(user["id"]), cid, role, email_clean)
        return AuthTokenResponse(access_token=token, user_id=user["id"], company_id=UUID(cid), role=role)
