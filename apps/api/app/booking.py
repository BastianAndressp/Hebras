"""Agendamiento de citas por WhatsApp: disponibilidad y reserva. Separado de services.py
igual que knowledge.py/knowledge_utils.py, para no seguir haciendo crecer ese archivo."""
from datetime import datetime, timedelta

from .services import DAY_MAP, get_business_hours, get_local_now


class SlotUnavailableError(Exception):
    """El horario pedido ya no está disponible (fuera de horario, o ya reservado)."""


class InvalidBookingRequestError(Exception):
    """La solicitud del modelo no se pudo interpretar (fecha/hora mal formada, etc.)."""


BOOKING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Consulta si un horario está disponible para un servicio. Usar antes de confirmar una cita con el cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Nombre del servicio solicitado, tal como lo dijo el cliente."},
                    "date": {"type": "string", "description": "Fecha deseada, formato YYYY-MM-DD."},
                    "time": {"type": "string", "description": "Hora deseada, formato HH:MM (24h), en la zona horaria del negocio."},
                },
                "required": ["service_name", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Reserva una cita ya confirmada explícitamente por el cliente (servicio, fecha y hora). No llamar sin esa confirmación explícita.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "HH:MM 24h"},
                    "customer_name": {"type": "string", "description": "Nombre del cliente para la reserva."},
                },
                "required": ["service_name", "date", "time", "customer_name"],
            },
        },
    },
]


def parse_local_datetime(setting, date_str: str, time_str: str) -> datetime:
    """Interpreta date/time (tal como los manda el modelo) en la zona horaria del bot."""
    tz = get_local_now(setting).tzinfo
    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise InvalidBookingRequestError(
            f"No entendí la fecha/hora '{date_str} {time_str}'. Usa el formato YYYY-MM-DD y HH:MM."
        ) from exc
    return naive.replace(tzinfo=tz)


async def list_active_services(conn, bot_id: str):
    return await conn.fetch(
        "select * from services where bot_id=$1 and active=true order by name", bot_id
    )


async def get_service_by_name(conn, bot_id: str, name: str):
    """Match case-insensitive exacto. Si no hay coincidencia, el caller le pasa al modelo
    la lista de servicios activos para que le pregunte al cliente cuál quiso decir, en vez
    de intentar adivinar con un match difuso que podría reservar el servicio equivocado."""
    return await conn.fetchrow(
        "select * from services where bot_id=$1 and active=true and lower(name)=lower($2)",
        bot_id, name,
    )


async def check_slot_available(conn, bot, setting, service, requested_start: datetime) -> tuple[bool, str]:
    """Retorna (disponible, motivo_si_no)."""
    now = get_local_now(setting)
    if requested_start < now:
        return False, "Ese horario ya pasó."

    requested_end = requested_start + timedelta(minutes=service["duration_minutes"])

    bh = get_business_hours(setting)
    if setting and setting["business_hours_enabled"] and "schedule" in bh:
        day_key = DAY_MAP.get(requested_start.weekday())
        day_config = bh.get("schedule", {}).get(day_key, {})
        if not day_config.get("active", True):
            return False, "Ese día no atendemos."
        start_str = day_config.get("start", "09:00")
        end_str = day_config.get("end", "18:00")
        req_start_str = requested_start.strftime("%H:%M")
        req_end_str = requested_end.strftime("%H:%M")
        if not (start_str <= req_start_str and req_end_str <= end_str):
            return False, f"Ese horario está fuera de nuestra atención ({start_str} a {end_str})."

    conflict = await conn.fetchval(
        """select 1 from appointments
           where bot_id=$1 and status='scheduled'
             and scheduled_start < $3 and scheduled_end > $2
           limit 1""",
        bot["id"], requested_start, requested_end,
    )
    if conflict:
        return False, "Ese horario ya está reservado."

    return True, ""


async def book_appointment(conn, bot, setting, service, customer_name, customer_phone,
                            requested_start: datetime, conversation_id=None):
    requested_end = requested_start + timedelta(minutes=service["duration_minutes"])
    async with conn.transaction():
        # Advisory lock por bot: un "select ... for update" sobre citas existentes no
        # sirve acá porque, en el caso normal, el horario pedido todavía NO tiene ninguna
        # fila con la que chocar -- el conflicto real es contra otra reserva concurrente
        # para ESE MISMO horario libre, que llega casi al mismo tiempo. Este lock
        # serializa todas las reservas de este bot (no solo las que se solapan), lo cual
        # es barato dado el volumen esperado de citas por negocio.
        await conn.execute("select pg_advisory_xact_lock(hashtext($1::text))", str(bot["id"]))
        ok, reason = await check_slot_available(conn, bot, setting, service, requested_start)
        if not ok:
            raise SlotUnavailableError(reason)
        return await conn.fetchrow(
            """insert into appointments(company_id, bot_id, service_id, conversation_id,
                   customer_name, customer_phone, scheduled_start, scheduled_end)
               values($1,$2,$3,$4,$5,$6,$7,$8)
               returning *""",
            bot["company_id"], bot["id"], service["id"], conversation_id,
            customer_name, customer_phone, requested_start, requested_end,
        )
