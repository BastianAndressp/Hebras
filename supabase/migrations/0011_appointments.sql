-- Agendamiento de citas por WhatsApp (barberías y negocios de servicios similares).
-- No hay tabla de disponibilidad nueva: se reutiliza settings.business_hours (ya es
-- jsonb por bot con horario semanal, ver 0002/0006) para no mantener dos fuentes de
-- horario que se puedan desincronizar entre sí.

create table services (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    bot_id uuid not null references bots(id) on delete cascade,
    name text not null,
    duration_minutes int not null check (duration_minutes > 0 and duration_minutes <= 480),
    price numeric(12,2),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index services_company_id_idx on services(company_id);
create index services_bot_id_idx on services(bot_id);

alter table services enable row level security;
create policy tenant_services on services
    using (company_id = current_company_id()) with check (company_id = current_company_id());

create type appointment_status as enum ('scheduled', 'canceled', 'completed');

-- service_id es "on delete restrict" a propósito: borrar un servicio con historial de
-- citas queda bloqueado; el dashboard solo permite desactivarlo (active=false).
create table appointments (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id) on delete cascade,
    bot_id uuid not null references bots(id) on delete cascade,
    service_id uuid not null references services(id) on delete restrict,
    conversation_id uuid references conversations(id) on delete set null,
    customer_name text not null,
    customer_phone text not null,
    scheduled_start timestamptz not null,
    scheduled_end timestamptz not null,
    status appointment_status not null default 'scheduled',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (scheduled_end > scheduled_start)
);
create index appointments_company_id_idx on appointments(company_id);
-- Sirve directo la consulta de solapamiento de horarios (bot_id + rango) que hace
-- check_slot_available; el filtro por status evita indexar citas canceladas/completadas
-- que nunca participan en el chequeo de disponibilidad.
create index appointments_bot_range_idx on appointments(bot_id, scheduled_start, scheduled_end)
    where status = 'scheduled';

alter table appointments enable row level security;
create policy tenant_appointments on appointments
    using (company_id = current_company_id()) with check (company_id = current_company_id());

-- Nota: sin "force row level security" (ver 0008) -- el pool elevado que usa worker.py
-- para ejecutar las tools de reserva del bot necesita escribir sin que RLS lo bloquee,
-- igual que ya ocurre para messages/conversations/usage. app_user sigue sujeto a RLS
-- igual, con o sin FORCE.
