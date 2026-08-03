import logging
import sys
import time
from contextlib import asynccontextmanager
import jwt
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .bootstrap import bootstrap_demo_data
from .config import settings
from .db import connect, disconnect
from .net import get_client_ip
from .queue import redis_client
from .admin_router import router as admin_router
from .auth_router import router as auth_router
from .knowledge import router as knowledge_router
from .routes import router as dashboard_router
from .team import router as team_router
from .webhooks import router as webhook_router

# Sin esto, los logs de los módulos de la app (auth_router, webhooks, etc.) nunca
# aparecían en `docker compose logs api` — solo los de uvicorn. Esto ocultaba, por
# ejemplo, el código de verificación de email en modo desarrollo y los errores reales
# de envío por Brevo.
logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect()
    if settings.demo_mode:
        # Nunca debe estar activo con datos reales: reinserta una empresa/bot demo
        # con UUIDs fijos en cada arranque, sobrescribiendo cualquier cambio manual.
        await bootstrap_demo_data()
    if not settings.openrouter_api_key or settings.openrouter_api_key == "change-me":
        log.warning(
            "OPENROUTER_API_KEY no está configurada: el RAG usará embeddings pseudo-aleatorios "
            "(sin significado semántico real) en vez de embeddings reales."
        )
    yield
    await disconnect()


app = FastAPI(title="Hebras", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Rate limiting respaldado en Redis (no en memoria del proceso), para que funcione
# correctamente con varias réplicas de "api" en paralelo (ver sección 12 del informe:
# colas y workers horizontales). Ventana fija por IP y, cuando hay sesión, también por
# tenant (company_id), para que un tenant ruidoso no consuma el cupo de otro.
RATE_LIMIT_WINDOW = 60  # segundos
MAX_REQUESTS_PER_WINDOW_IP = 120
MAX_REQUESTS_PER_WINDOW_TENANT = 300


async def _under_rate_limit(key: str, limit: int) -> bool:
    redis = await redis_client()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_WINDOW)
    return count <= limit


def _company_id_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return str(claims.get("company_id")) or None
    except jwt.InvalidTokenError:
        return None


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    window = int(time.time() // RATE_LIMIT_WINDOW)
    client_ip = get_client_ip(request)

    if not await _under_rate_limit(f"ratelimit:ip:{client_ip}:{window}", MAX_REQUESTS_PER_WINDOW_IP):
        return Response("Too Many Requests", status_code=429)

    company_id = _company_id_from_request(request)
    if company_id and not await _under_rate_limit(f"ratelimit:tenant:{company_id}:{window}", MAX_REQUESTS_PER_WINDOW_TENANT):
        return Response("Too Many Requests", status_code=429)

    return await call_next(request)


app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(dashboard_router)
app.include_router(team_router)
app.include_router(knowledge_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

