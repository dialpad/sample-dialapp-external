"""The in-memory access tokens and the short-lived OAuth results."""

from backend.stores import OAUTH_RESULT_TTL_SECONDS
from backend.stores import AccessTokens
from backend.stores import OAuthResults
from backend.stores import UserKey

JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_a_user_gets_the_same_access_token_every_time_and_other_users_get_other_tokens() -> None:
  tokens = AccessTokens()

  first = tokens.issue(JANE)

  assert tokens.issue(JANE) == first
  assert tokens.issue(PAT) != first
  assert tokens.lookup(first) == JANE


def test_an_unknown_access_token_maps_to_no_user() -> None:
  assert AccessTokens().lookup('never-issued') is None


class Clock:
  """A settable clock."""
  def __init__(self) -> None:
    self.now = 1_000.0

  def __call__(self) -> float:
    return self.now


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
