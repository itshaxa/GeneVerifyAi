"""Tests for database initialization and the synthetic seed mechanism."""

from datetime import date

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.database.base import Base
from app.database.init import init_db
from app.database.seed import (
    DEMO_MATCH_CNIC,
    DEMO_MISMATCH_CNIC,
    DEMO_REVIEW_CNIC,
    GENERATED_RECORD_COUNT,
    seed_database,
)
from app.models import DnaProfile, IdentityRecord, IdentityStatus
from app.services import dna_service
from app.services.str_engine.panel import STR_PANEL

EXPECTED_TOTAL = GENERATED_RECORD_COUNT + 3  # generated records + demo trio


def test_init_db_creates_tables(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'init_check.db'}")
    init_db(bind=engine)
    tables = set(inspect(engine).get_table_names())
    assert {"identity_records", "dna_profiles"} <= tables
    engine.dispose()


def test_seed_creates_at_least_100_records(seeded_session: Session) -> None:
    count = seeded_session.scalar(select(func.count(IdentityRecord.id)))
    assert count is not None and count >= 100
    assert count == EXPECTED_TOTAL


def test_seed_creates_one_dna_profile_per_identity(seeded_session: Session) -> None:
    profiles = seeded_session.scalar(select(func.count(DnaProfile.id)))
    identities = seeded_session.scalar(select(func.count(IdentityRecord.id)))
    assert profiles == identities


def test_cnic_unique_constraint(seeded_session: Session) -> None:
    duplicate = IdentityRecord(
        cnic=DEMO_MATCH_CNIC,
        name="Duplicate Person",
        father_name="Duplicate Father",
        date_of_birth=date(2000, 1, 1),
        gender="male",  # type: ignore[arg-type]
        address="Synthetic Street 0, Block A, Demoville",
    )
    seeded_session.add(duplicate)
    with pytest.raises(IntegrityError):
        seeded_session.flush()
    seeded_session.rollback()


def test_rerunning_seed_does_not_duplicate(db_session: Session) -> None:
    first = seed_database(db_session)
    second = seed_database(db_session)

    assert first.created == EXPECTED_TOTAL
    assert second.created == 0
    assert second.skipped == EXPECTED_TOTAL

    count = db_session.scalar(select(func.count(IdentityRecord.id)))
    assert count == EXPECTED_TOTAL


def test_seed_is_deterministic(db_session: Session) -> None:
    seed_database(db_session)
    markers_run_a = {
        record.cnic: record.dna_profile.markers
        for record in db_session.scalars(select(IdentityRecord)).all()
        if record.dna_profile is not None
    }

    # Rebuild the same dataset in a second database and compare.
    engine_b = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine_b)
    session_b = sessionmaker(bind=engine_b, expire_on_commit=False)()
    seed_database(session_b)
    markers_run_b = {
        record.cnic: record.dna_profile.markers
        for record in session_b.scalars(select(IdentityRecord)).all()
        if record.dna_profile is not None
    }

    assert markers_run_a == markers_run_b
    session_b.close()
    engine_b.dispose()


def test_every_profile_contains_expected_markers_with_two_alleles(seeded_session: Session) -> None:
    profiles = seeded_session.scalars(select(DnaProfile)).all()
    assert profiles
    for profile in profiles:
        assert set(profile.markers.keys()) == set(STR_PANEL)
        for marker, alleles in profile.markers.items():
            assert len(alleles) == 2, f"{marker} must have exactly two alleles"
            assert all(isinstance(value, (int, float)) and value > 0 for value in alleles)


def test_demo_records_exist_with_expected_status(seeded_session: Session) -> None:
    match = seeded_session.scalar(
        select(IdentityRecord).where(IdentityRecord.cnic == DEMO_MATCH_CNIC)
    )
    mismatch = seeded_session.scalar(
        select(IdentityRecord).where(IdentityRecord.cnic == DEMO_MISMATCH_CNIC)
    )
    review = seeded_session.scalar(
        select(IdentityRecord).where(IdentityRecord.cnic == DEMO_REVIEW_CNIC)
    )
    assert match is not None and match.status is IdentityStatus.ACTIVE
    assert mismatch is not None and mismatch.status is IdentityStatus.ACTIVE
    assert review is not None and review.status is IdentityStatus.UNDER_REVIEW


def test_demo_match_and_mismatch_profiles_differ(seeded_session: Session) -> None:
    match_id = seeded_session.scalar(
        select(IdentityRecord.id).where(IdentityRecord.cnic == DEMO_MATCH_CNIC)
    )
    mismatch_id = seeded_session.scalar(
        select(IdentityRecord.id).where(IdentityRecord.cnic == DEMO_MISMATCH_CNIC)
    )
    assert match_id is not None and mismatch_id is not None

    match_markers = dna_service.get_reference_markers_by_identity_id(seeded_session, match_id)
    mismatch_markers = dna_service.get_reference_markers_by_identity_id(seeded_session, mismatch_id)
    assert match_markers is not None and mismatch_markers is not None
    assert match_markers != mismatch_markers


def test_dna_service_returns_validated_markers(seeded_session: Session) -> None:
    identity = seeded_session.scalar(
        select(IdentityRecord).where(IdentityRecord.cnic == DEMO_MATCH_CNIC)
    )
    assert identity is not None
    markers = dna_service.get_reference_markers_by_identity_id(seeded_session, identity.id)
    assert markers is not None
    assert set(markers) == set(STR_PANEL)
