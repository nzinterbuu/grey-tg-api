"""Tenant list, create, and update."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from callback_dispatch import start_dispatcher, stop_dispatcher
from database import get_session
from models.tenant import Tenant
from models.tenant_auth import TenantAuth
from schemas import CreateTenantRequest, TenantResponse, UpdateTenantRequest

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _tenant_response(t: Tenant) -> TenantResponse:
    return TenantResponse(
        id=str(t.id),
        name=t.name,
        callback_url=t.callback_url,
        created_at=t.created_at.isoformat() if t.created_at else "",
    )


@router.get("", response_model=list[TenantResponse])
def list_tenants(db: Session = Depends(get_session)) -> list[TenantResponse]:
    rows = db.execute(select(Tenant).order_by(Tenant.created_at.desc())).scalars().all()
    return [_tenant_response(r) for r in rows]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_session)) -> TenantResponse:
    row = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Tenant not found."})
    return _tenant_response(row)


@router.post("", response_model=TenantResponse, status_code=201)
def create_tenant(
    body: CreateTenantRequest,
    db: Session = Depends(get_session),
) -> TenantResponse:
    cb = (body.callback_url or "").strip() or None
    t = Tenant(name=body.name.strip(), callback_url=cb)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _tenant_response(t)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    body: UpdateTenantRequest,
    db: Session = Depends(get_session),
) -> TenantResponse:
    """Update an existing tenant (name and/or callback_url). If callback_url changes and the tenant is authorized, the inbound dispatcher is restarted with the new URL."""
    row = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Tenant not found."})
    if body.name is None and body.callback_url is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "Provide at least one of name or callback_url."},
        )
    old_callback = row.callback_url
    if body.name is not None:
        row.name = body.name.strip()
    if body.callback_url is not None:
        row.callback_url = (body.callback_url.strip() or None)
    db.commit()
    db.refresh(row)
    # Restart dispatcher if callback_url changed and tenant is authorized
    if old_callback != row.callback_url:
        auth = db.execute(select(TenantAuth).where(TenantAuth.tenant_id == tenant_id)).scalars().first()
        if auth and auth.authorized:
            await stop_dispatcher(tenant_id)
            if row.callback_url:
                await start_dispatcher(tenant_id, row.callback_url)
    return _tenant_response(row)
