"""
app/api/institutions.py
"""

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db
from app.deps_auth import get_current_user, require_admin, require_institution_admin
from app.models.user import User
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionUpdate,
    InstitutionResponse,
    InstitutionListResponse,
    AddMemberRequest,
    MemberListResponse,
)
from app.schemas.user import UserResponse
from app.services import institution_service
from app.core.exceptions import AuthorizationError

router = APIRouter(prefix="/institutions", tags=["Institutions"])


@router.post("/", response_model=InstitutionResponse, status_code=201, summary="Create institution")
def create_institution(
    payload: InstitutionCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new institution. Requires super_admin role.
    """
    institution = institution_service.create_institution(db, payload)
    return InstitutionResponse.model_validate(institution)


@router.get("/", response_model=InstitutionListResponse, summary="List institutions")
def list_institutions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=1000),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all institutions. Requires super_admin role.
    """
    institutions, total = institution_service.list_institutions(db, skip=skip, limit=limit)
    return InstitutionListResponse(
        items=[InstitutionResponse.model_validate(i) for i in institutions],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{institution_id}", response_model=InstitutionResponse, summary="Get institution")
def get_institution(
    institution_id: uuid.UUID,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    Get an institution by ID.
    institution_admin can only view their own institution. super_admin can view any.
    """
    if user.role != "super_admin" and user.institution_id != institution_id:
        raise AuthorizationError("You don't have access to this institution")
    
    institution = institution_service.get_institution(db, institution_id)
    return InstitutionResponse.model_validate(institution)


@router.patch("/{institution_id}", response_model=InstitutionResponse, summary="Update institution")
def update_institution(
    institution_id: uuid.UUID,
    payload: InstitutionUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update an institution. Requires super_admin role.
    """
    institution = institution_service.update_institution(db, institution_id, payload)
    return InstitutionResponse.model_validate(institution)


@router.post("/{institution_id}/activate", response_model=InstitutionResponse, summary="Activate institution")
def activate_institution(
    institution_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Activate an institution. Requires super_admin role.
    """
    institution = institution_service.activate_institution(db, institution_id)
    return InstitutionResponse.model_validate(institution)


@router.post("/{institution_id}/deactivate", response_model=InstitutionResponse, summary="Deactivate institution")
def deactivate_institution(
    institution_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deactivate an institution. Requires super_admin role.
    """
    institution = institution_service.deactivate_institution(db, institution_id)
    return InstitutionResponse.model_validate(institution)


@router.get("/{institution_id}/members", response_model=MemberListResponse, summary="List members")
def list_members(
    institution_id: uuid.UUID,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    List members of an institution. 
    institution_admin can only view members of their own institution.
    """
    if user.role != "super_admin" and user.institution_id != institution_id:
        raise AuthorizationError("You don't have access to this institution's members")
    
    members = institution_service.list_members(db, institution_id)
    return MemberListResponse(
        items=[UserResponse.model_validate(m) for m in members]
    )


@router.post("/{institution_id}/members", response_model=UserResponse, summary="Add member")
def add_member(
    institution_id: uuid.UUID,
    payload: AddMemberRequest,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    Add a user to an institution.
    """
    if user.role != "super_admin" and user.institution_id != institution_id:
        raise AuthorizationError("You don't have access to add members to this institution")
    
    member = institution_service.add_member(db, institution_id, payload)
    return UserResponse.model_validate(member)


@router.delete("/{institution_id}/members/{user_id}", summary="Remove member")
def remove_member(
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a member from an institution.
    """
    if user.role != "super_admin" and user.institution_id != institution_id:
        raise AuthorizationError("You don't have access to remove members from this institution")
    
    institution_service.remove_member(db, institution_id, user_id)
    return {"message": "Member removed"}
