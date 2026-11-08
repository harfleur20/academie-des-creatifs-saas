"""The four identity records of a school are created once, even by parallel first visits."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import OrganizationRecord
from app.services import school_branding
from app.services.school_branding import IDENTITY_RECORDS, get_or_create_identity_records


def file_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def new_school(engine) -> int:
    with Session(engine) as db:
        org = OrganizationRecord(name="Nouvelle école", slug="nouvelle-ecole", subdomain="nouvelle-ecole")
        db.add(org)
        db.commit()
        return org.id


def rows_per_record(engine, org_id) -> list[int]:
    with Session(engine) as db:
        return [
            db.scalar(select(func.count()).select_from(model).where(model.organization_id == org_id))
            for model, _defaults in IDENTITY_RECORDS
        ]


def test_the_first_visit_creates_the_four_records_once(tmp_path):
    engine = file_engine(tmp_path)
    org_id = new_school(engine)
    with Session(engine, autoflush=False) as db:
        first = get_or_create_identity_records(db, db.get(OrganizationRecord, org_id))
    with Session(engine, autoflush=False) as db:
        second = get_or_create_identity_records(db, db.get(OrganizationRecord, org_id))
    assert [record.id for record in second] == [record.id for record in first]
    assert first[0].site_name == "Nouvelle école"
    assert rows_per_record(engine, org_id) == [1, 1, 1, 1]


def test_a_visit_that_loses_the_race_reuses_the_winner_records(tmp_path, monkeypatch):
    engine = file_engine(tmp_path)
    org_id = new_school(engine)
    winner = []
    real_find = school_branding._find_identity_record

    def read_then_let_the_other_visit_finish(db, model, organization_id):
        found = real_find(db, model, organization_id)
        if not winner:
            winner.append(None)  # the parallel visit below must not trigger itself again
            # This visit has just found nothing; the parallel visit now creates and commits everything.
            with Session(engine, autoflush=False) as other:
                winner[:] = [record.id for record in get_or_create_identity_records(other, other.get(OrganizationRecord, org_id))]
        return found

    monkeypatch.setattr(school_branding, "_find_identity_record", read_then_let_the_other_visit_finish)
    with Session(engine, autoflush=False) as db:
        org = db.get(OrganizationRecord, org_id)
        org.contact_email = "contact@nouvelle-ecole.test"  # work of the request, still pending
        records = get_or_create_identity_records(db, org)
        assert [record.id for record in records] == winner
        db.commit()

    assert rows_per_record(engine, org_id) == [1, 1, 1, 1]
    with Session(engine) as db:
        assert db.get(OrganizationRecord, org_id).contact_email == "contact@nouvelle-ecole.test"
