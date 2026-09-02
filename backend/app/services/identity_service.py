"""Identity lookup business logic.

Security rule: identities are ONLY retrievable by exact CNIC. This module
never exposes list/export operations on the identity table.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cnic import InvalidCnicError, normalize_cnic
from app.models.identity import IdentityRecord

logger = logging.getLogger(__name__)


class IdentityNotFoundError(LookupError):
    """Raised when no synthetic identity record matches the CNIC."""

    def __init__(self, cnic: str) -> None:
        super().__init__(f"No synthetic identity record found for CNIC {cnic}")
        self.cnic = cnic


def find_identity_by_cnic(db: Session, raw_cnic: str) -> IdentityRecord:
    """Return exactly one synthetic identity record for a valid CNIC.

    Raises:
        InvalidCnicError: malformed CNIC input.
        IdentityNotFoundError: well-formed CNIC with no matching record.
    """
    cnic = normalize_cnic(raw_cnic)
    record = db.execute(
        select(IdentityRecord).where(IdentityRecord.cnic == cnic)
    ).scalar_one_or_none()
    if record is None:
        logger.info("Identity lookup miss for CNIC %s", cnic)
        raise IdentityNotFoundError(cnic)
    return record
