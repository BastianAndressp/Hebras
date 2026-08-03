create extension if not exists vector;

alter type member_role add value if not exists 'solo-lectura';

alter table document_chunks add column if not exists embedding vector(1536);

create index if not exists document_chunks_embedding_idx on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null unique references companies(id) on delete cascade,
  whatsapp_access_token text,
  whatsapp_app_secret text,
  openrouter_api_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists settings (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null unique references companies(id) on delete cascade,
  bot_id uuid not null unique references bots(id) on delete cascade,
  business_hours_enabled boolean not null default false,
  business_hours jsonb not null default '{"timezone":"UTC","schedule":{"mon":{"start":"09:00","end":"18:00","active":true},"tue":{"start":"09:00","end":"18:00","active":true},"wed":{"start":"09:00","end":"18:00","active":true},"thu":{"start":"09:00","end":"18:00","active":true},"fri":{"start":"09:00","end":"18:00","active":true},"sat":{"start":"10:00","end":"14:00","active":false},"sun":{"start":"10:00","end":"14:00","active":false}}}',
  out_of_hours_message text not null default 'Gracias por escribirnos. En este momento estamos fuera de nuestro horario de atención. Te responderemos tan pronto estemos disponibles.',
  monthly_spending_limit_usd numeric(12,2) not null default 100.00 check (monthly_spending_limit_usd >= 0),
  default_language text not null default 'es',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  title text not null,
  message text not null,
  severity text not null default 'info' check (severity in ('info', 'warning', 'error')),
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists notifications_company_unread_idx on notifications(company_id, is_read, created_at desc);

alter table api_keys enable row level security;
alter table settings enable row level security;
alter table notifications enable row level security;

create policy tenant_api_keys on api_keys using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_settings on settings using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_notifications on notifications using (company_id = current_company_id()) with check (company_id = current_company_id());
