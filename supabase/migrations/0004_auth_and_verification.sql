-- Migración 0004: Autenticación nativa y validación de correo electrónico

create table if not exists app_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  company_name text not null default 'Mi Empresa',
  is_email_verified boolean not null default false,
  verification_code text,
  verification_expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists app_users_email_idx on app_users(email);
create index if not exists app_users_verification_code_idx on app_users(verification_code);

alter table app_users enable row level security;

create policy app_users_policy on app_users
  using (id = current_company_id() or is_email_verified = true);
