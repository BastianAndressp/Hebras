-- Migración 0007: planes en CLP + prueba gratuita de 7 días + anti-abuso
--
-- Contexto: la facturación era decorativa (cambiar de plan no cobraba nada) y no existía
-- ningún concepto de prueba gratuita. Esta migración deja la base lista para:
--   1. Planes en pesos chilenos en vez de USD.
--   2. Una suscripción 'trialing' de 7 días creada en el signup, con expiración derivada
--      al leer (sin cron: el proyecto no tiene ningún job programado).
--   3. Anti-abuso: qué número de WhatsApp ya consumió una prueba (barrera dura) y qué
--      IP/dispositivo se usó al registrarse (señal blanda, nunca bloqueo permanente).
--
-- Nota de diseño: whatsapp_number_claims y signup_events NO llevan RLS forzada como el
-- resto de las tablas de tenant (ver 0005). Son, por diseño, consultas CROSS-tenant: hay
-- que poder verificar si un número o una IP ya se usó bajo OTRA empresa, así que se
-- acceden con el pool elevado (igual que webhook_events), nunca con tenant_conn.

-- 1. Precios en CLP -----------------------------------------------------------------
alter table plans rename column base_price_usd to price_amount;
alter table plans add column currency text not null default 'CLP';

update plans set price_amount = 9990 where slug = 'starter';
update plans set price_amount = 19990 where slug = 'pro';
update plans set price_amount = 39990 where slug = 'business';

-- 2. Estado de suscripción validado + campo de trial --------------------------------
alter table subscriptions add column trial_ends_at timestamptz;

-- Todo lo existente hoy es 'active' (ver hallazgo del análisis), así que el CHECK no
-- rompe datos ya cargados.
alter table subscriptions add constraint subscriptions_status_check
  check (status in ('trialing', 'active', 'trial_expired', 'canceled'));

create index if not exists subscriptions_trialing_idx
  on subscriptions(status, trial_ends_at) where status = 'trialing';

-- 3. Barrera dura: un número de WhatsApp ya usado no vuelve a dar prueba ------------
create table whatsapp_number_claims (
  phone_number_id text primary key,
  company_id uuid references companies(id) on delete set null,
  first_claimed_at timestamptz not null default now(),
  trial_consumed boolean not null default true
);

-- 4. Anti-abuso blando: huella de IP/dispositivo por registro -----------------------
create table signup_events (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  ip_hash text not null,
  user_agent_hash text,
  company_id uuid references companies(id) on delete set null,
  created_at timestamptz not null default now(),
  flagged boolean not null default false
);

create index if not exists signup_events_ip_hash_created_idx
  on signup_events(ip_hash, created_at desc);
