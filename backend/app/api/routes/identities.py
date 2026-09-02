"""CNIC identity lookup endpoint.

Security design: there is NO list/export endpoint for identities. The only
read path is an exact-CNIC lookup returning a single safe record.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.cnic import InvalidCnicError
from app.database.session import get_db
from app.models.user import User
from app.schemas.identity import IdentityLookupResponse
from app.services import identity_service

router = APIRouter()


@router.get(
    "/{cnic}",
    response_model=IdentityLookupResponse,
    summary="Look up one synthetic identity by exact CNIC (authenticated)",
    responses={
        401: {"description": "Missing or invalid authentication"},
        404: {"description": "No synthetic identity record with this CNIC"},
        422: {"description": "Malformed CNIC format"},
    },
)
def lookup_identity(
    cnic: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IdentityLookupResponse:
    """Return the single synthetic identity matching the CNIC, or 404."""
    del current_user  # Authentication is enforced by the dependency itself.
    try:
        record = identity_service.find_identity_by_cnic(db, cnic)
    except InvalidCnicError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except identity_service.IdentityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return IdentityLookupResponse.model_validate(record)
