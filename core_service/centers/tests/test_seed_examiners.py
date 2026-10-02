"""
Tests for the seed_examiners management command.
"""
from __future__ import annotations

import pytest
from django.core.management import call_command

from centers.management.commands.seed_examiners import ROSTER, SPEC_ALIASES


def _seed_catalog():
    from catalog.models import Instrument

    for name, style in SPEC_ALIASES.values():
        Instrument.objects.get_or_create(name=name, style=style)


def _make_center(pk_name="Test Center"):
    from centers.models import ExamCenter

    return ExamCenter.objects.create(
        name=pk_name, city="Hanoi", address="1 Test St"
    )


@pytest.mark.django_db
def test_seed_examiners_creates_full_roster():
    from centers.models import Examiner

    _seed_catalog()
    center = _make_center()

    call_command("seed_examiners", "--center", str(center.pk))

    examiners = Examiner.objects.filter(center=center)
    assert examiners.count() == len(ROSTER)
    # every active examiner has at least one specialization
    for e in examiners.filter(is_active=True):
        assert e.specializations.count() >= 1


@pytest.mark.django_db
def test_seed_examiners_is_idempotent():
    from centers.models import Examiner

    _seed_catalog()
    center = _make_center()

    call_command("seed_examiners", "--center", str(center.pk))
    call_command("seed_examiners", "--center", str(center.pk))

    assert Examiner.objects.filter(center=center).count() == len(ROSTER)


@pytest.mark.django_db
def test_seed_examiners_scoped_clear():
    from centers.models import Examiner

    _seed_catalog()
    center_a = _make_center("Center A")
    center_b = _make_center("Center B")

    call_command("seed_examiners", "--center", str(center_a.pk))
    call_command("seed_examiners", "--center", str(center_b.pk))
    assert Examiner.objects.filter(center=center_a).count() == len(ROSTER)

    # Clearing center_a must not touch center_b.
    call_command("seed_examiners", "--center", str(center_a.pk), "--clear")

    assert Examiner.objects.filter(center=center_a).count() == len(ROSTER)
    assert Examiner.objects.filter(center=center_b).count() == len(ROSTER)
