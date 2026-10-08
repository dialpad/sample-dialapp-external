"""The short-lived in-memory OAuth results (acme_dialpad_rightbar/stores.py)."""

from acme_dialpad_rightbar.stores import OAUTH_RESULT_TTL_SECONDS
from acme_dialpad_rightbar.stores import OAuthResults
from acme_dialpad_rightbar.stores import UserKey
from tests.conftest import Clock

JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_an_oauth_result_is_consumed_once_by_the_user_it_was_recorded_for() -> None:
  results = OAuthResults(Clock())
  results.record(JANE)

  assert not results.consume(PAT)
  assert results.consume(JANE)
  assert not results.consume(JANE)


def test_an_oauth_result_expires_after_five_minutes() -> None:
  clock = Clock()
  results = OAuthResults(clock)
  results.record(JANE)
  clock.now += OAUTH_RESULT_TTL_SECONDS

  assert not results.consume(JANE)
