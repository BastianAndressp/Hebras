-- Migración 0005: Rol de aplicación sin bypass de RLS + RLS forzada en tablas de tenant
--
-- Hasta ahora la Row Level Security definida en 0001/0002 nunca se aplicaba en la práctica:
-- el backend se conectaba con el rol dueño de las tablas (o un superusuario), a quien
-- Postgres exime de RLS salvo que se use FORCE ROW LEVEL SECURITY. El aislamiento
-- multi-tenant dependía 100% de que cada query en la app incluyera "where company_id=$1" a
-- mano. Esta migración crea un rol de aplicación de bajo privilegio y fuerza RLS en las
-- tablas de negocio, para que un bug de una query sin ese filtro ya no pueda filtrar datos
-- entre empresas: queda como defensa en profundidad a nivel de base de datos.
--
-- IMPORTANTE: la contraseña de abajo es un valor de desarrollo, igual que WEBHOOK_VERIFY_TOKEN
-- o WHATSAPP_APP_SECRET en .env.example. Antes de producción: ALTER ROLE app_user PASSWORD
-- '...' con un valor fuerte, y actualizar TENANT_DATABASE_URL en el entorno del backend.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_user') then
    create role app_user login password 'app_user_change_me_in_prod';
  end if;
end
$$;

grant usage on schema public to app_user;
grant select, insert, update, delete on all tables in schema public to app_user;
grant usage, select on all sequences in schema public to app_user;
alter default privileges in schema public grant select, insert, update, delete on tables to app_user;
alter default privileges in schema public grant usage, select on sequences to app_user;

-- Tablas de negocio con company_id: RLS forzada incluso para el dueño de la tabla.
alter table companies force row level security;
alter table memberships force row level security;
alter table subscriptions force row level security;
alter table bots force row level security;
alter table handoff_rules force row level security;
alter table knowledge_bases force row level security;
alter table documents force row level security;
alter table document_chunks force row level security;
alter table conversations force row level security;
alter table messages force row level security;
alter table usage force row level security;
alter table audit_logs force row level security;
alter table api_keys force row level security;
alter table settings force row level security;
alter table notifications force row level security;

-- plans NO se fuerza: es catálogo global sin company_id, su policy ya permite
-- lectura de cualquier plan activo para cualquier sesión.
