from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from .auth import Principal, require_owner, require_principal
from .db import tenant_conn
from .schemas import TeamMemberCreate, TeamMemberResponse, TeamMemberUpdate

router = APIRouter(prefix="/v1/team", tags=["team"])


@router.get("/members", response_model=list[TeamMemberResponse])
async def list_members(principal: Principal = Depends(require_principal)):
    async with tenant_conn(principal.company_id) as conn:
        rows = await conn.fetch(
            """select id, user_id, role, created_at
                 from memberships
                where company_id = $1::uuid
                order by created_at asc""",
            principal.company_id,
        )
    return [dict(row) for row in rows]


@router.post("/members", response_model=TeamMemberResponse)
async def add_member(payload: TeamMemberCreate, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        try:
            row = await conn.fetchrow(
                """insert into memberships(company_id, user_id, role)
                   values($1::uuid, $2::uuid, $3::member_role)
                   on conflict (company_id, user_id) do update set role = excluded.role
                   returning id, user_id, role, created_at""",
                principal.company_id,
                str(payload.user_id),
                payload.role,
            )
            await conn.execute(
                "insert into audit_logs(company_id, actor_id, action) values($1::uuid, $2::uuid, 'team.member.added')",
                principal.company_id,
                principal.user_id,
            )
        except Exception as exc:
            raise HTTPException(400, f"Error al agregar miembro: {exc}") from exc
    return dict(row)


@router.put("/members/{user_id}", response_model=TeamMemberResponse)
async def update_member(user_id: str, payload: TeamMemberUpdate, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    async with tenant_conn(principal.company_id) as conn:
        try:
            row = await conn.fetchrow(
                """update memberships
                       set role = $1::member_role
                     where company_id = $2::uuid and user_id = $3::uuid
                   returning id, user_id, role, created_at""",
                payload.role,
                principal.company_id,
                user_id,
            )
        except Exception as exc:
            raise HTTPException(400, f"Error al actualizar miembro: {exc}") from exc
        if not row:
            raise HTTPException(404, "Member not found")
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1::uuid, $2::uuid, 'team.member.updated')",
            principal.company_id,
            principal.user_id,
        )
    return dict(row)


@router.delete("/members/{user_id}")
async def delete_member(user_id: str, principal: Principal = Depends(require_principal)):
    require_owner(principal)
    if user_id == principal.user_id:
        raise HTTPException(400, "You cannot remove your own membership")
    async with tenant_conn(principal.company_id) as conn:
        try:
            result = await conn.execute(
                "delete from memberships where company_id = $1::uuid and user_id = $2::uuid",
                principal.company_id,
                user_id,
            )
        except Exception as exc:
            raise HTTPException(400, f"Error al eliminar miembro: {exc}") from exc
        if result.endswith(" 0"):
            raise HTTPException(404, "Member not found")
        await conn.execute(
            "insert into audit_logs(company_id, actor_id, action) values($1::uuid, $2::uuid, 'team.member.removed')",
            principal.company_id,
            principal.user_id,
        )
    return {"ok": True}