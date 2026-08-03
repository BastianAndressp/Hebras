-- Migración 0003: Soporte Multi-Bot por empresa y refuerzo de roles

-- 1. Eliminar la restricción UNIQUE por company_id en bots para permitir múltiples bots por empresa
alter table bots drop constraint if exists bots_company_id_key;

-- 2. Crear índice compuesto en bots(company_id)
create index if not exists bots_company_id_idx on bots(company_id);

-- 3. Asegurar que los bots pertenezcan a la empresa y el número de teléfono sea único por bot
-- (phone_number_id ya es UNIQUE en bots)

-- 4. Asegurar que el rol solo-lectura esté disponible en member_role
do $$
begin
  if not exists (select 1 from pg_enum join pg_type on pg_enum.enumtypid = pg_type.oid where pg_type.typname = 'member_role' and enumlabel = 'solo-lectura') then
    alter type member_role add value 'solo-lectura';
  end if;
exception
  when duplicate_object then null;
end
$$;
