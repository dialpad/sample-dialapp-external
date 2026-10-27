"""The short-lived in-memory OAuth results (acme_dialpad_rightbar/demo/oauth_results.py)."""

from acme_dialpad_rightbar.context import UserKey
from acme_dialpad_rightbar.demo.oauth_results import OAUTH_RESULT_TTL_SECONDS
from acme_dialpad_rightbar.demo.oauth_results import OAuthResults
from tests.conftest import Clock

JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_an_oauth_result_is_consumed_once_by_its_user_and_expires_after_five_minutes() -> None:
  clock = Clock()
  results = OAuthResults(clock)
  results.record(JANE)

  assert not results.consume(PAT)
  assert results.consume(JANE)
  assert not results.consume(JANE)

  results.record(JANE)
  clock.now += OAUTH_RESULT_TTL_SECONDS
  assert not results.consume(JANE)
