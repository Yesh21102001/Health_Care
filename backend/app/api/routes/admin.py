"""Admin endpoints. Require role=admin (read from the database on every request).
No endpoint here returns conversation or report content."""

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbDep, SettingsDep
from app.api.errors import ApiError
from app.schemas.health import AdminUserOut, AdminUsersResponse, UpdateRoleRequest
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
async def dashboard(admin: AdminUser, db: DbDep, settings: SettingsDep) -> dict:
    return await admin_service.dashboard(db, settings)


@router.get("/users", response_model=AdminUsersResponse)
async def users(
    admin: AdminUser,
    db: DbDep,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
):
    rows, total = await admin_service.list_users(db, q, page, page_size)
    return AdminUsersResponse(
        users=[
            AdminUserOut(
                id=str(u["_id"]),
                name=u["name"],
                email=u["email"],
                role=u["role"],
                created_at=u["created_at"],
                conversation_count=u["conversation_count"],
            )
            for u in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}")
async def update_role(user_id: str, body: UpdateRoleRequest, admin: AdminUser, db: DbDep) -> dict:
    try:
        user = await admin_service.set_role(db, admin.id, user_id, body.role)
    except admin_service.AdminActionError as exc:
        raise ApiError(exc.status, exc.message) from None
    return {"user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"], "role": user["role"]}}


@router.get("/audit")
async def audit(admin: AdminUser, db: DbDep) -> dict:
    return {"entries": await admin_service.audit_entries(db)}
