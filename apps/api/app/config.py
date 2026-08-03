from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://postgres:postgres@localhost:5432/whatsapp_ai"
    # Rol de base de datos sin BYPASSRLS (ver migración 0005), usado por las rutas del
    # dashboard autenticadas para que la Row Level Security definida en el esquema sea una
    # barrera real y no solo documental (defensa en profundidad ante un "where company_id"
    # olvidado). Debe apuntar al rol app_user, no al superusuario de database_url.
    tenant_database_url: str = Field(min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    webhook_verify_token: str = "change-me"
    whatsapp_app_secret: str = "change-me"
    whatsapp_access_token: str = "change-me"
    whatsapp_phone_number_id: str = "100000000000000"
    whatsapp_graph_version: str = "v23.0"
    openrouter_api_key: str = "change-me"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    brevo_api_key: str | None = None
    email_from: str = "bot@example.com"
    # Obligatorio: sin esto la app no arranca. Antes se permitía vacío y se saltaba la
    # verificación de firma del JWT por completo (ver auth.py), aceptando cualquier token.
    jwt_secret: str = Field(min_length=16)
    # Obligatorio: clave Fernet (32 bytes urlsafe-base64) usada para cifrar api_keys en reposo.
    # Generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    app_encryption_key: str = Field(min_length=16)
    # Si es true, bootstrap.py siembra datos demo con UUIDs fijos en cada arranque.
    # Debe estar en false en cualquier entorno con datos reales.
    demo_mode: bool = False
    # CIDRs separados por coma desde los que se confía en X-Forwarded-For para resolver
    # la IP real del cliente (ver net.py::get_client_ip). Vacío por defecto: sin un
    # reverse proxy real declarado, nunca hay que confiar en ese header porque cualquier
    # cliente puede falsificarlo. Configurar solo si en producción se pone un proxy
    # delante de esta API (ej. "10.0.0.0/8" para la red interna de ese proxy).
    trusted_proxy_networks: str = ""
    # Duración de la prueba gratuita otorgada al registrarse (plan Pro).
    trial_days: int = 7
    # Tope de mensajes durante la prueba, independiente del tope del plan Pro (1000):
    # suficiente para evaluar el producto de verdad, poco atractivo para quien solo
    # quiera exprimir pruebas gratis.
    trial_message_cap: int = 200
    # Cuentas nuevas por IP (hasheada) por día antes de responder 429. Deliberadamente
    # generoso (no es la barrera dura, ver whatsapp_number_claims) porque en Chile
    # muchos clientes reales comparten IP por CGNAT.
    signup_ip_daily_limit: int = 3
    # Cuentas históricas acumuladas por la misma IP antes de marcar (flagged=true) para
    # revisión manual, sin bloquear.
    signup_flag_threshold: int = 5
    # Token compartido para los endpoints /v1/admin/* (activar suscripciones a mano
    # mientras no hay pasarela de pago). Sin esto configurado, esos endpoints responden
    # 503 en vez de aceptar cualquier request. Generar con: openssl rand -base64 32
    platform_admin_token: str | None = None
    # A dónde llegan los avisos de "un cliente pidió upgrade de plan" (cobro manual).
    platform_admin_email: str | None = None
    # Si es true, la API corre el loop del worker (worker.py::listen) como tarea de
    # fondo dentro del mismo proceso, en vez de esperar un servicio "worker" aparte.
    # Pensado para plataformas donde un Background Worker separado cuesta extra (ej.
    # Render, que no tiene plan gratuito para ese tipo de servicio) y el volumen de
    # mensajes no justifica escalar la API y el worker por separado todavía.
    run_worker_in_process: bool = False


settings = Settings()


