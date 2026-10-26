"""Test-only app factory for the browser stack (C02). It serves the unchanged production API
(`sentinel.api.create_app`) with a deterministic fixture investigator. Production code never
imports this module.

The fixture investigator behaves exactly like DeterministicInvestigator, except that a case
whose transaction amount is PROVIDER_FAILURE_MINOR fails with `provider_unavailable`, every
time. It makes no model or network call.

The scorer comes from the production `scorers.from_environment()` (I01): SENTINEL_SCORER is
unset/`rule` or a registered model key; anything else fails startup. No artifact path is
ever taken from the environment or a request.
"""
from __future__ import annotations

import os
import uuid

from sentinel import scorers
from sentinel.api import create_app as production_app
from sentinel.investigators import DeterministicInvestigator, InvestigatorError
from sentinel.scoring import artifact
from sentinel.service import Sentinel

PROVIDER_FAILURE_MINOR = 777_777


class FixtureInvestigator(DeterministicInvestigator):
    def __init__(self):
        super().__init__()
        self.config = artifact("deterministic-fixture-investigator", "x1", {
            "kind": "deterministic-fixture", "base": "deterministic-investigator/i1",
            "provider_unavailable_when_amount_minor": PROVIDER_FAILURE_MINOR,
        })
        self.principal_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"sentinel:agent:{self.config.name}:{self.config.sha256}")

    def investigate(self, view):
        if view.facts.get("amount_minor") == PROVIDER_FAILURE_MINOR:
            raise InvestigatorError("provider_unavailable")
        return super().investigate(view)


def create_app():
    return production_app(Sentinel(os.environ["SENTINEL_DATABASE_URL"], FixtureInvestigator(),
                                   scorer=scorers.from_environment()))


def create_app_never_ready():
    """Test-only: an app factory that never finishes starting (readiness-timeout tests)."""
    import time
    time.sleep(3600)
