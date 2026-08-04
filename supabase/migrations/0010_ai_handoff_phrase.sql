-- Frase que, si aparece en la respuesta que la IA genera (no en el mensaje del
-- cliente), dispara la derivación automática a humano. Es un mecanismo distinto de
-- las "keywords" existentes (que se buscan en el mensaje ENTRANTE del cliente): esta
-- frase la define el propio prompt del bot como su forma de anunciar que deriva
-- ("Te paso con un trabajador de Basfer para que te ayude directamente."), y el
-- backend la detecta después de generar y enviar la respuesta.
alter table handoff_rules add column if not exists ai_handoff_phrase text;
