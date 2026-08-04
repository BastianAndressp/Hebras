# Hebras — MVP

Hebras es una plataforma SaaS multi-tenant de asistentes de IA para WhatsApp. Incluye webhook seguro de Meta, procesamiento asíncrono, derivación a humano, dashboard, soporte multi-bot por empresa y aislamiento por tenant reforzado con Row Level Security.

## Inicio rápido

1. Copia `.env.example` a `.env` y completa las credenciales de Meta y OpenRouter.
2. Genera los tres secretos obligatorios (sin ellos la app no arranca):
   ```bash
   # JWT_SECRET
   openssl rand -base64 48
   # APP_ENCRYPTION_KEY (debe ser una clave Fernet válida: 32 bytes urlsafe-base64)
   openssl rand -base64 32
   ```
   Pégalos en `JWT_SECRET` y `APP_ENCRYPTION_KEY` en `.env`.
3. Ejecuta `docker compose up --build`. Esto aplica automáticamente todas las migraciones (`supabase/migrations/0001` a `0007`) sobre el contenedor de Postgres, incluyendo la creación del rol `app_user` (ver Seguridad más abajo). Si ya tenías un volumen de Postgres de una versión anterior, las migraciones nuevas no se aplican solas — hay que correrlas a mano: `docker compose exec -T db psql -U postgres -d whatsapp_ai < supabase/migrations/0007_trials_and_pricing.sql`.
4. Abre `http://localhost:3000`, regístrate (queda un flujo de verificación por código de email; el registro arranca automáticamente una prueba gratuita de 7 días, ver "Planes y prueba gratuita" más abajo) y configura en Meta la URL `https://TU_DOMINIO/webhooks/whatsapp`.

### Envío de email (Brevo)

- Si `BREVO_API_KEY` no está configurada, el código de verificación solo queda logueado en la consola del servicio `api` (`docker compose logs api`).
- Brevo (a diferencia de Resend) permite verificar un **remitente individual** sin necesidad de dominio propio: entra a tu cuenta de [brevo.com](https://www.brevo.com) → *Senders, Domains & Dedicated IPs* → *Senders* → agrega el correo que quieras usar como remitente y confirma el enlace que te llega. Ese mismo correo va en `EMAIL_FROM`.
- Sin un remitente verificado, o con una `BREVO_API_KEY` inválida, Brevo rechaza el envío; el error queda logueado en `api` y el código de verificación sigue disponible como respaldo en ese mismo log.

`DEMO_MODE=true` (ver `.env`) siembra una empresa/bot de ejemplo con UUIDs fijos en cada arranque — solo para desarrollo local. Debe quedar en `false` en cualquier entorno con datos reales, porque sobrescribe esos registros en cada reinicio.

## Diseño operativo

- `GET /webhooks/whatsapp`: verificación challenge de Meta.
- `POST /webhooks/whatsapp`: exige firma `X-Hub-Signature-256` válida (responde 503/403 si no); deduplica y encola, nunca espera al LLM. La firma se valida con el **Meta App Secret de la empresa dueña del número** (cargado desde el dashboard, pestaña "API Keys / OpenRouter"), no con una variable de entorno global — cada empresa trae su propia app de Meta. `WHATSAPP_APP_SECRET` en `.env` solo queda como fallback para un despliegue de un solo tenant / demo.
- El worker usa el `phone_number_id` de cada mensaje para resolver el bot dueño; si no hay match, el mensaje se descarta (nunca se enruta al bot de otra empresa).
- Las derivaciones a humano se marcan en el inbox y se notifican por email cuando se configura Brevo.

## Planes y prueba gratuita

- Tres planes en CLP: Starter (9.990, 300 msgs/mes), Pro (19.990, 1.000 msgs/mes), Business (39.990, 3.000 msgs/mes).
- Cada cuenta nueva arranca con una prueba gratuita de `TRIAL_DAYS` días (7 por defecto) en el plan Pro, con un tope de `TRIAL_MESSAGE_CAP` mensajes (200 por defecto, independiente del tope del plan). El vencimiento se calcula al leer (`trial_ends_at` vs. `now()`), no hay ningún cron: una fila puede seguir diciendo `status='trialing'` en la base y mostrarse como vencida (`trial_expired`) igual.
- Al vencer la prueba (o agotar la cuota, o no tener suscripción), el bot **deja de responder** — sin marcar la conversación como derivada a humano, y sin borrar nada — hasta que se activa un plan. El dashboard muestra un aviso claro con los días restantes o el estado vencido.
- **Barrera dura anti-abuso**: un número de WhatsApp (`phone_number_id` real, no el placeholder `pending-...` que trae un bot recién creado) solo otorga una prueba gratuita una vez, sin importar cuántas cuentas nuevas se creen — se registra en `whatsapp_number_claims` al conectar el número (`PUT /v1/bot`, `POST /v1/bots`).
- **Señal blanda anti-abuso**: `SIGNUP_IP_DAILY_LIMIT` (3 por defecto) cuentas nuevas por IP por día antes de responder 429 — deliberadamente generoso porque los ISP móviles chilenos comparten IP por CGNAT. Correos de dominios desechables (mailinator, guerrillamail, etc.) se rechazan directamente. Ninguna de estas señales bloquea permanentemente: solo frenan creación masiva y marcan (`flagged`) cuentas sospechosas para revisión manual.
- **Sin pasarela de pago todavía**: `POST /v1/billing/request-upgrade` no activa el plan, solo registra la solicitud y avisa por email a `PLATFORM_ADMIN_EMAIL`. Para activarlo de verdad: `POST /v1/admin/subscriptions/{company_id}/activate` con el header `X-Admin-Token: $PLATFORM_ADMIN_TOKEN`:
  ```bash
  curl -X POST http://localhost:8000/v1/admin/subscriptions/<company_id>/activate \
    -H "X-Admin-Token: $PLATFORM_ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"plan_id": "<plan_id>", "period_days": 30}'
  ```
  Sin `PLATFORM_ADMIN_TOKEN` configurado, estos endpoints responden 503.

## Multi-bot

Una empresa puede tener varios bots, cada uno con su propio número de WhatsApp (`phone_number_id`), prompt, base de conocimiento (RAG) y horarios de atención. Se gestionan desde la pestaña "Config IA" del dashboard (crear, cambiar entre bots con el selector del header, eliminar — no se puede eliminar el único bot de la empresa) o vía API: `GET/POST /v1/bots`, `DELETE /v1/bots/{id}`. Los endpoints por-bot (`/v1/bot`, `/v1/handoff-rule`, `/v1/settings`, `/v1/knowledge/*`) aceptan un query param `?bot_id=` opcional; sin él, caen al primer bot creado (compatibilidad con empresas de un solo bot).

## Citas

El bot puede agendar citas dentro de la conversación de WhatsApp, sin menú rígido — el cliente pide hora, el bot chequea disponibilidad real y confirma. Para activarlo:

1. En el dashboard, pestaña **"Citas"**, agrega al menos un servicio (nombre, duración en minutos, precio opcional). Sin servicios activos, el bot conversa normal pero nunca intenta agendar nada.
2. Configura el horario de atención en la pestaña **"Horarios"** (usa el mismo `settings.business_hours` de siempre — no hay una configuración de disponibilidad separada). Con `business_hours_enabled` apagado, el bot puede agendar a cualquier hora.
3. El bot decide solo cuándo ofrecer una hora y cuándo confirmar la reserva (tool-calling estándar de OpenAI/OpenRouter — `check_availability` y `book_appointment`, ver `apps/api/app/booking.py`). Valida que el horario pedido caiga dentro del horario configurado y no choque con otra cita ya agendada del mismo bot.
4. Las citas quedan visibles (y se pueden cancelar manualmente) en la misma pestaña "Citas" del dashboard.

**v1 = solo crear citas.** Cancelar o reagendar por WhatsApp todavía no existe — se maneja desde el dashboard o por teléfono. No hay integración con Google Calendar ni ningún calendario externo.

## Seguridad

- **Secretos obligatorios**: `JWT_SECRET`, `APP_ENCRYPTION_KEY` y `TENANT_DATABASE_URL` deben estar configurados o la app no arranca (antes, un `JWT_SECRET` vacío desactivaba silenciosamente la verificación de firma de los tokens).
- **Row Level Security real**: las rutas autenticadas del dashboard se conectan a Postgres con el rol `app_user` (creado en la migración `0005_app_role_and_rls.sql`), que no tiene `BYPASSRLS`. Esto hace que el aislamiento por `company_id` sea una barrera de base de datos, no solo un `where` en cada query. Antes de producción: `ALTER ROLE app_user PASSWORD '...'` con un valor fuerte y actualizar `TENANT_DATABASE_URL` en el entorno del backend (el valor por defecto en `.env.example` es solo para desarrollo).
- **`api_keys` cifradas en reposo**: los tokens de WhatsApp/OpenRouter que cada empresa carga desde el dashboard se cifran con Fernet (`APP_ENCRYPTION_KEY`) antes de guardarse.
- **Webhook de Meta**: rechaza cualquier request sin un Meta App Secret configurado (de la empresa dueña del número, o el global de `.env` como fallback) o sin firma válida — ya no acepta payloads sin verificar por omisión. El verify token del handshake `GET` también es por empresa: se autogenera y se ve en la pestaña "WhatsApp Meta" del dashboard (`GET /v1/webhook-info`), con `WEBHOOK_VERIFY_TOKEN` de `.env` como fallback global.
- **Rate limiting**: respaldado en Redis (no en memoria del proceso), por IP y por tenant, para funcionar correctamente con varias réplicas de `api`.
- **IP real del cliente**: el navegador le habla directo a la API (`NEXT_PUBLIC_API_URL` se hornea en el build del dashboard, ver `docker-compose.yml`), no a través del proxy same-origin de Next.js — antes todo el tráfico se veía como la IP del contenedor del dashboard. Si en producción se pone un reverse proxy real delante, hay que declarar sus redes en `TRUSTED_PROXY_NETWORKS` para que `X-Forwarded-For` se respete (por defecto no se confía en ese header desde ningún origen).

## Base de conocimiento (RAG)

Si `OPENROUTER_API_KEY` no está configurada con una key real, los embeddings se generan de forma pseudo-aleatoria (determinística mediante hash, sin significado semántico) y la búsqueda por similitud degrada a un fallback por coincidencia de términos. Para RAG semántico real, configura una `OPENROUTER_API_KEY` válida — la app lo advierte en el log de arranque si falta.

## Tests

```bash
cd apps/api
pip install -r requirements-dev.txt
python -m pytest -q
```

Los tests de integración (`test_multibot.py`, `test_trial.py`, `test_trial_abuse.py`, `test_worker_blocking.py`) requieren una Postgres real alcanzable vía `DATABASE_URL` (la que levanta `docker compose`); si no está disponible, se saltan automáticamente. El resto de la suite es unitaria y no necesita base de datos.

Para el piloto, los bots y teléfonos se pueden crear también asistidamente mediante SQL o la API administrativa. Las credenciales de producción deben inyectarse como secretos, nunca desde el dashboard de un entorno compartido.
