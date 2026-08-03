create extension if not exists pgcrypto;

create type member_role as enum ('owner', 'staff');
create type bot_status as enum ('active', 'paused', 'disconnected');
create type conversation_status as enum ('active', 'handoff', 'closed');
create type message_direction as enum ('inbound', 'outbound');

create table companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table plans (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  monthly_message_limit integer not null check (monthly_message_limit > 0),
  base_price_usd numeric(12,2) not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table subscriptions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null unique references companies(id) on delete cascade,
  plan_id uuid not null references plans(id),
  status text not null default 'active',
  current_period_start date not null default date_trunc('month', now())::date,
  current_period_end date not null default (date_trunc('month', now()) + interval '1 month')::date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into plans (slug, name, monthly_message_limit, base_price_usd) values
  ('starter', 'Starter', 300, 29.00),
  ('pro', 'Pro', 1000, 79.00),
  ('business', 'Business', 3000, 149.00);

create table memberships (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  user_id uuid not null,
  role member_role not null default 'staff',
  created_at timestamptz not null default now(),
  unique(company_id, user_id)
);

create table bots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  name text not null,
  phone_number_id text not null unique,
  system_prompt text not null,
  model text not null default 'deepseek/deepseek-chat',
  fallback_model text,
  temperature numeric(2,1) not null default 0.4 check (temperature between 0 and 1),
  max_tokens integer not null default 400 check (max_tokens between 50 and 500),
  monthly_message_limit integer not null default 500 check (monthly_message_limit > 0),
  status bot_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id)
);

create table handoff_rules (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  bot_id uuid not null unique references bots(id) on delete cascade,
  keywords text[] not null default '{}',
  max_bot_attempts integer not null default 2 check (max_bot_attempts between 1 and 10),
  notification_email text,
  created_at timestamptz not null default now()
);

create table knowledge_bases (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  bot_id uuid not null unique references bots(id) on delete cascade,
  name text not null default 'Base de conocimiento',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table documents (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  knowledge_base_id uuid not null references knowledge_bases(id) on delete cascade,
  title text not null,
  source_type text not null default 'manual',
  source_text text not null,
  status text not null default 'ready',
  chunk_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  created_at timestamptz not null default now(),
  unique(document_id, chunk_index)
);

create table conversations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  bot_id uuid not null references bots(id) on delete cascade,
  contact_phone text not null,
  status conversation_status not null default 'active',
  created_at timestamptz not null default now(),
  last_message_at timestamptz not null default now(),
  unique(bot_id, contact_phone)
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  conversation_id uuid not null references conversations(id) on delete cascade,
  direction message_direction not null,
  content text not null,
  meta_message_id text unique,
  token_count integer not null default 0,
  estimated_cost_usd numeric(12,6) not null default 0,
  created_at timestamptz not null default now()
);

create table usage (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  period_start date not null,
  messages_count bigint not null default 0,
  tokens_count bigint not null default 0,
  cost_usd numeric(12,6) not null default 0,
  unique(company_id, period_start)
);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  actor_id uuid,
  action text not null,
  created_at timestamptz not null default now()
);

create table webhook_events (
  id uuid primary key default gen_random_uuid(),
  meta_message_id text not null unique,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create index conversations_company_last_message_idx on conversations(company_id, last_message_at desc);
create index messages_company_created_idx on messages(company_id, created_at desc);
create index messages_conversation_created_idx on messages(conversation_id, created_at);
create index plans_active_idx on plans(is_active, monthly_message_limit);
create index subscriptions_company_idx on subscriptions(company_id, status);
create index knowledge_bases_company_bot_idx on knowledge_bases(company_id, bot_id);
create index documents_company_created_idx on documents(company_id, created_at desc);
create index document_chunks_company_created_idx on document_chunks(company_id, created_at desc);
create index document_chunks_document_idx on document_chunks(document_id, chunk_index);

alter table companies enable row level security;
alter table memberships enable row level security;
alter table plans enable row level security;
alter table subscriptions enable row level security;
alter table bots enable row level security;
alter table handoff_rules enable row level security;
alter table knowledge_bases enable row level security;
alter table documents enable row level security;
alter table document_chunks enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table usage enable row level security;
alter table audit_logs enable row level security;

create function current_company_id() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'company_id', '')::uuid
$$;

create policy tenant_companies on companies using (id = current_company_id());
create policy tenant_memberships on memberships using (company_id = current_company_id());
create policy tenant_plans on plans using (is_active = true);
create policy tenant_subscriptions on subscriptions using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_bots on bots using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_handoff_rules on handoff_rules using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_knowledge_bases on knowledge_bases using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_documents on documents using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_document_chunks on document_chunks using (company_id = current_company_id()) with check (company_id = current_company_id());
create policy tenant_conversations on conversations using (company_id = current_company_id());
create policy tenant_messages on messages using (company_id = current_company_id());
create policy tenant_usage on usage using (company_id = current_company_id());
create policy tenant_audit_logs on audit_logs using (company_id = current_company_id());

