import pytest


# These two pre-existing tests validate live-room tenancy/time-window behavior with
# a minimal teacher fixture that predates professional onboarding. Readiness itself
# is covered separately in test_teacher_readiness.py, so keep the concerns isolated
# instead of weakening the production gate.
_LEGACY_LIVE_TESTS = {
    "test_live_class_join_requires_own_school_membership_and_course_window",
    "test_live_class_start_is_teacher_owned_and_time_gated",
}


@pytest.fixture(autouse=True)
def isolate_legacy_live_tests_from_teacher_onboarding(request, monkeypatch):
    if request.node.name in _LEGACY_LIVE_TESTS:
        monkeypatch.setattr(
            "app.services.live_classes.require_teacher_ready",
            lambda db, tenant: None,
        )
