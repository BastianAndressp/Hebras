-- Migración 0006: horarios/límite de gasto por bot, no por empresa
--
-- La tabla settings (0002) referencia bot_id pero además tenía unique(company_id),
-- lo que en la práctica limitaba a una sola fila de configuración por empresa sin
-- importar cuántos bots tuviera. Para que cada bot tenga sus propios horarios de
-- atención y límite de gasto (soporte multi-bot, ver 0003), se elimina esa
-- restricción y se deja unique(bot_id) como única llave.

alter table settings drop constraint if exists settings_company_id_key;
