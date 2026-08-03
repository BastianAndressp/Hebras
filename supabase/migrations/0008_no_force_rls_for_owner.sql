-- En desarrollo local, DATABASE_URL usa el rol "postgres", un superusuario real que
-- siempre se salta RLS sin importar FORCE ROW LEVEL SECURITY (los superusuarios están
-- exentos de RLS por invariante de Postgres, no por la ausencia de FORCE).
--
-- En proveedores de Postgres administrado (Render, y probablemente Supabase/RDS/etc.),
-- el usuario que provee DATABASE_URL es dueño de las tablas pero NO es superusuario real
-- (no tiene BYPASSRLS ni puede otorgárselo: "must be superuser to change bypassrls
-- attribute"). Con FORCE ROW LEVEL SECURITY activo (migración 0005), Postgres aplica RLS
-- incluso al dueño de la tabla, lo que rompe cualquier operación del pool "elevado" de la
-- app (signup, procesamiento del webhook) que necesita escribir sin un company_id de
-- sesión: "new row violates row-level security policy for table companies".
--
-- Quitar FORCE no debilita el aislamiento de app_user: RLS sigue aplicándose por completo
-- a app_user (no es el dueño ni superusuario, con o sin FORCE). FORCE solo decide si el
-- propio dueño de la tabla queda sujeto a RLS o no — y ese dueño es exactamente el rol que
-- el pool elevado de la app necesita usar sin restricciones, igual que el superusuario
-- local.
alter table companies no force row level security;
alter table memberships no force row level security;
alter table subscriptions no force row level security;
alter table bots no force row level security;
alter table handoff_rules no force row level security;
alter table knowledge_bases no force row level security;
alter table documents no force row level security;
alter table document_chunks no force row level security;
alter table conversations no force row level security;
alter table messages no force row level security;
alter table usage no force row level security;
alter table audit_logs no force row level security;
alter table api_keys no force row level security;
alter table settings no force row level security;
alter table notifications no force row level security;
