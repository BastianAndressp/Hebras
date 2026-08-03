-- Cada empresa trae su propia app de Meta (su propio WHATSAPP_APP_SECRET), no una
-- compartida a nivel de plataforma: el "Meta App Secret" que ya se cargaba desde
-- ApiKeysTab (api_keys.whatsapp_app_secret) se guardaba pero nunca se usaba para
-- validar la firma HMAC del webhook -- solo se miraba una variable de entorno global,
-- que obligaba al operador de la plataforma a configurarla a mano por cada cliente.
-- Este campo nuevo guarda el verify token (autogenerado, ver GET /v1/webhook-info) que
-- cada empresa debe pegar en Meta al configurar SU webhook -- necesario porque, a
-- diferencia del app secret, este token no viaja en el payload del mensaje: llega en
-- un GET sin ningún company_id identificable, así que hay que poder buscarlo por valor.
alter table api_keys add column if not exists whatsapp_verify_token text;
