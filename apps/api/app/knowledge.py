from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from .auth import Principal, require_owner, require_principal
from .db import tenant_conn
from .schemas import DocumentCreate, DocumentResponse, DocumentUploadResponse
from .knowledge_utils import extract_text_from_upload
from .services import store_document

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


async def get_bot(conn, company_id: str, bot_id: str | None = None):
    if bot_id:
        bot = await conn.fetchrow("select * from bots where id=$1 and company_id=$2", bot_id, company_id)
    else:
        bot = await conn.fetchrow("select * from bots where company_id=$1 order by created_at limit 1", company_id)
    if not bot:
        raise HTTPException(404, "No bot configured")
    return bot


async def get_or_create_knowledge_base(conn, bot_id: str, company_id: str):
    kb = await conn.fetchrow("select * from knowledge_bases where bot_id=$1", bot_id)
    if kb:
        return kb
    return await conn.fetchrow(
        """insert into knowledge_bases(company_id, bot_id, name)
           values($1,$2,'Base de conocimiento') returning *""",
        company_id, bot_id,
    )


@router.get("/documents")
async def list_documents(bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        knowledge_base = await get_or_create_knowledge_base(conn, bot["id"], principal.company_id)
        rows = await conn.fetch(
            """select id, title, status, chunk_count, created_at
                 from documents
                where knowledge_base_id=$1
                order by created_at desc""",
            knowledge_base["id"],
        )
    return [dict(row) for row in rows]


@router.post("/documents", response_model=DocumentResponse)
async def create_document(payload: DocumentCreate, bot_id: str | None = Query(default=None), principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        knowledge_base = await get_or_create_knowledge_base(conn, bot["id"], principal.company_id)
        document, _chunks = await store_document(conn, principal.company_id, knowledge_base["id"], payload.title, payload.content)
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1,$2,'knowledge.document.created')",
            principal.company_id,
            principal.user_id,
        )
    return dict(document)


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    principal: Principal = Depends(require_principal),
    bot_id: str | None = Query(default=None),
    title: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    require_owner(principal)
    raw = await file.read()
    content = extract_text_from_upload(file.filename or "documento", file.content_type, raw)
    if not content:
        raise HTTPException(400, "No se pudo extraer texto del archivo")

    document_title = title.strip() if title and title.strip() else (file.filename or "Documento")
    async with tenant_conn(principal.company_id) as conn:
        bot = await get_bot(conn, principal.company_id, bot_id)
        knowledge_base = await get_or_create_knowledge_base(conn, bot["id"], principal.company_id)
        document, _chunks = await store_document(conn, principal.company_id, knowledge_base["id"], document_title, content, source_type=file.content_type or "upload")
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1,$2,'knowledge.document.uploaded')",
            principal.company_id,
            principal.user_id,
        )
    return dict(document)