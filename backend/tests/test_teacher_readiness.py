import pytest

from app.models.teacher_onboarding import TeacherProfessionalProfileRecord
from app.services.phone_numbers import normalize_whatsapp_phone
from app.services.teacher_readiness import teacher_profile_complete


def complete_profile() -> TeacherProfessionalProfileRecord:
    return TeacherProfessionalProfileRecord(
        organization_id=1,
        user_id=1,
        professional_title="Motion Designer",
        experience_years=4,
        activity_domains=["Motion design"],
        bio="Je conçois et anime des formations créatives adaptées aux apprenants.",
        skills=["After Effects"],
        languages=["Français"],
        whatsapp_phone="+237677123456",
        whatsapp_country="CM",
        city="Douala",
        country="Cameroun",
        portfolio_url="https://portfolio.example.com",
    )


def test_teacher_profile_requires_whatsapp_teaching_language_and_location() -> None:
    profile = complete_profile()
    assert teacher_profile_complete(profile) is True

    profile.whatsapp_phone = None
    assert teacher_profile_complete(profile) is False

    profile.whatsapp_phone = "+237677123456"
    profile.languages = []
    assert teacher_profile_complete(profile) is False

    profile.languages = ["Français"]
    profile.city = None
    assert teacher_profile_complete(profile) is False

    profile.city = "Douala"
    profile.country = None
    assert teacher_profile_complete(profile) is False


def test_current_phone_number_is_normalized_to_e164() -> None:
    phone, legacy = normalize_whatsapp_phone("06 12 34 56 78", "FR")
    assert phone == "+33612345678"
    assert legacy is False


def test_historical_african_number_is_preserved_for_future_whatsapp_verification() -> None:
    phone, legacy = normalize_whatsapp_phone("77 12 34 56", "CM")
    assert phone == "+23777123456"
    assert legacy is True


def test_invalid_phone_number_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_whatsapp_phone("12", "FR")
