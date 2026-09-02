"""Deterministic synthetic dataset seeding.

All identity and DNA records created here are fictional demonstration data.
Names are generated from synthetic name lists, CNICs use the never-issued
``99900`` demo prefix, and every value is derived from a fixed RNG seed so
the same dataset is reproduced on every run and environment.

Usage (from the ``backend/`` directory):

    python -m app.database.seed

The operation is idempotent: records whose CNIC already exists are skipped,
so re-running never creates duplicates.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dna_profile import DnaProfile
from app.models.identity import Gender, IdentityRecord, IdentityStatus
from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL, validate_str_markers

#: Fixed RNG seed — change only if the whole demo dataset should change.
SEED = 20260828
#: Never-issued demo prefix; guarantees no overlap with real CNIC series.
DEMO_CNIC_PREFIX = "99900"
GENERATED_RECORD_COUNT = 120

# Demo CNICs (SYNTHETIC DEMO IDENTIFIERS ONLY — documented in the README).
DEMO_MATCH_CNIC = "99900-0000001-1"
DEMO_MISMATCH_CNIC = "99900-0000002-3"
DEMO_REVIEW_CNIC = "99900-0000003-5"

_MALE_FIRST_NAMES = (
    "Aariz", "Bilal", "Daniyal", "Ehsan", "Fahad", "Hamza", "Ibrahim", "Jawad",
    "Kamran", "Luqman", "Mikail", "Nabeel", "Omair", "Parvaiz", "Qasim",
    "Rehan", "Saad", "Taimoor", "Umair", "Zubair",
)
_FEMALE_FIRST_NAMES = (
    "Ayesha", "Bushra", "Dua", "Farah", "Hina", "Iqra", "Javeria", "Khadija",
    "Lubna", "Mahnoor", "Nadia", "Rabia", "Sadia", "Tahira", "Uzma", "Zainab",
)
_FAMILY_NAMES = (
    "Ahmedyar", "Bakhshiar", "Chandiar", "Dostiar", "Faridar", "Gulshani",
    "Haidari", "Iqbaliyar", "Jalandri", "Kambari", "Mehrdad", "Nooriani",
    "Qalandri", "Roshani", "Siyali", "Tamkini",
)
_DEMO_CITIES = ("Demoville", "Synthabad", "Prototown", "Hackacity")
_DOB_START = date(1960, 1, 1)
_DOB_SPAN_DAYS = 16_800  # ~46 years of birth dates

# Fixed reference STR profiles for the presentation demo records.
_DEMO_MATCH_MARKERS: dict[str, list[int]] = {
    "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24], "D8S1179": [12, 13],
    "D21S11": [29, 30], "D18S51": [14, 16], "D5S818": [10, 11], "D13S317": [9, 11],
    "D7S820": [9, 10], "CSF1PO": [10, 11], "TH01": [7, 9], "TPOX": [8, 11],
    "D16S539": [11, 12], "D2S1338": [19, 21], "D19S433": [13, 14], "D12S391": [20, 22],
    "D10S1248": [14, 15], "D1S1656": [13, 16], "D22S1045": [16, 17], "SE33": [22, 24],
}
_DEMO_MISMATCH_MARKERS: dict[str, list[int]] = {
    "D3S1358": [14, 17], "vWA": [15, 19], "FGA": [20, 25], "D8S1179": [10, 14],
    "D21S11": [28, 33], "D18S51": [13, 18], "D5S818": [9, 12], "D13S317": [8, 12],
    "D7S820": [8, 11], "CSF1PO": [9, 12], "TH01": [6, 8], "TPOX": [9, 12],
    "D16S539": [10, 13], "D2S1338": [18, 23], "D19S433": [12, 15], "D12S391": [19, 24],
    "D10S1248": [13, 16], "D1S1656": [12, 17], "D22S1045": [15, 18], "SE33": [20, 27],
}
_DEMO_REVIEW_MARKERS: dict[str, list[int]] = {
    "D3S1358": [16, 18], "vWA": [16, 20], "FGA": [22, 26], "D8S1179": [11, 15],
    "D21S11": [30, 34], "D18S51": [15, 20], "D5S818": [8, 13], "D13S317": [10, 13],
    "D7S820": [9, 12], "CSF1PO": [11, 13], "TH01": [8, 10], "TPOX": [10, 12],
    "D16S539": [9, 13], "D2S1338": [20, 24], "D19S433": [14, 16], "D12S391": [21, 25],
    "D10S1248": [14, 16], "D1S1656": [14, 18], "D22S1045": [17, 19], "SE33": [23, 29],
}


@dataclass(frozen=True)
class SeedSummary:
    created: int
    skipped: int
    total: int


def _digits(cnic: str) -> str:
    return cnic.replace("-", "")


def _generate_markers(rng: random.Random) -> dict[str, list[int]]:
    markers: dict[str, list[int]] = {}
    for marker in STR_PANEL:
        low, high = ALLELE_RANGES[marker]
        alleles = sorted(rng.randint(low, high) for _ in range(2))
        markers[marker] = alleles
    return markers


def _build_demo_spec(
    cnic: str,
    name: str,
    gender: Gender,
    status: IdentityStatus,
    markers: dict[str, list[int]],
) -> dict:
    return {
        "cnic": cnic,
        "name": name,
        "father_name": "Kamal Demoosh",
        "date_of_birth": date(1990, 3, 14),
        "gender": gender,
        "address": "Synthetic Street 1, Block A, Demoville",
        "photo_reference": f"synthetic-photo://{_digits(cnic)}",
        "status": status,
        "markers": markers,
    }


def _demo_specs() -> list[dict]:
    return [
        _build_demo_spec(
            DEMO_MATCH_CNIC, "Sami Demoosh", Gender.MALE, IdentityStatus.ACTIVE,
            _DEMO_MATCH_MARKERS,
        ),
        _build_demo_spec(
            DEMO_MISMATCH_CNIC, "Lina Demoosh", Gender.FEMALE, IdentityStatus.ACTIVE,
            _DEMO_MISMATCH_MARKERS,
        ),
        _build_demo_spec(
            DEMO_REVIEW_CNIC, "Omar Demoosh", Gender.MALE, IdentityStatus.UNDER_REVIEW,
            _DEMO_REVIEW_MARKERS,
        ),
    ]


def _generated_spec(index: int) -> dict:
    """Deterministically derive one synthetic record from (SEED, index)."""
    rng = random.Random(SEED + index)

    gender = Gender.MALE if rng.random() < 0.5 else Gender.FEMALE
    first_name = rng.choice(
        _MALE_FIRST_NAMES if gender is Gender.MALE else _FEMALE_FIRST_NAMES
    )
    family_name = rng.choice(_FAMILY_NAMES)
    father_first = rng.choice(_MALE_FIRST_NAMES)

    # Demo CNIC: 99900-NNNNNNN-N, sequential middle block, gender-style last digit.
    middle = f"{1_000_000 + index:07d}"
    last_digit = rng.choice([1, 3, 5, 7, 9] if gender is Gender.MALE else [2, 4, 6, 8])
    cnic = f"{DEMO_CNIC_PREFIX}-{middle}-{last_digit}"

    block = chr(ord("A") + rng.randint(0, 5))
    city = rng.choice(_DEMO_CITIES)
    return {
        "cnic": cnic,
        "name": f"{first_name} {family_name}",
        "father_name": f"{father_first} {family_name}",
        "date_of_birth": _DOB_START + timedelta(days=rng.randint(0, _DOB_SPAN_DAYS)),
        "gender": gender,
        "address": f"Synthetic Street {rng.randint(1, 250)}, Block {block}, {city}",
        "photo_reference": f"synthetic-photo://{_digits(cnic)}",
        "status": IdentityStatus.ACTIVE,
        "markers": _generate_markers(rng),
    }


def _all_specs(generated_count: int) -> list[dict]:
    return _demo_specs() + [_generated_spec(i) for i in range(generated_count)]


def seed_database(session: Session, generated_count: int = GENERATED_RECORD_COUNT) -> SeedSummary:
    """Idempotently seed the deterministic demo dataset.

    Existing CNICs are skipped, so repeated runs never duplicate records.
    """
    existing_cnics = set(session.scalars(select(IdentityRecord.cnic)).all())

    created = 0
    skipped = 0
    for spec in _all_specs(generated_count):
        if spec["cnic"] in existing_cnics:
            skipped += 1
            continue
        markers = validate_str_markers(spec["markers"])
        identity = IdentityRecord(
            cnic=spec["cnic"],
            name=spec["name"],
            father_name=spec["father_name"],
            date_of_birth=spec["date_of_birth"],
            gender=spec["gender"],
            address=spec["address"],
            photo_reference=spec["photo_reference"],
            status=spec["status"],
        )
        identity.dna_profile = DnaProfile(
            profile_code=f"STRP-{_digits(spec['cnic'])}",
            markers=markers,
        )
        session.add(identity)
        created += 1

    session.commit()
    count = len(session.scalars(select(IdentityRecord.id)).all())
    return SeedSummary(created=created, skipped=skipped, total=count)


def main() -> None:
    """CLI entry point: initialize schema (non-destructive) and seed data."""
    from app.database.init import init_db
    from app.database.session import SessionLocal

    init_db()
    with SessionLocal() as session:
        summary = seed_database(session)

    print("GeneVerify AI synthetic dataset seed complete.")
    print(f"  created: {summary.created}")
    print(f"  skipped (already present): {summary.skipped}")
    print(f"  total identity records: {summary.total}")
    print(f"  demo CNICs: {DEMO_MATCH_CNIC} (match), {DEMO_MISMATCH_CNIC} (mismatch), {DEMO_REVIEW_CNIC} (review)")


if __name__ == "__main__":
    main()
