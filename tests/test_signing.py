"""The signed state and connection cookie: forged, expired, wrong-purpose, wrong-user values."""

from backend import signing
from backend.signing import COOKIE_MAX_AGE_SECONDS
from backend.signing import STATE_TTL_SECONDS

SECRET = 'app-secret'
NOW = 1_000_000.0


def test_state_round_trips_the_user_it_was_issued_for() -> None:
  state = signing.issue_state(5432, 12345, SECRET, NOW)

  claims = signing.verify_state(state, SECRET, NOW + 1)

  assert claims is not None
  assert (claims.user_id, claims.company_id) == (5432, 12345)


def test_state_expires_after_ten_minutes() -> None:
  state = signing.issue_state(5432, 12345, SECRET, NOW)

  assert signing.verify_state(state, SECRET, NOW + STATE_TTL_SECONDS - 1) is not None
  assert signing.verify_state(state, SECRET, NOW + STATE_TTL_SECONDS) is None


def test_state_signed_with_another_secret_is_rejected() -> None:
  state = signing.issue_state(5432, 12345, 'someone-elses-secret', NOW)

  assert signing.verify_state(state, SECRET, NOW) is None


def test_state_with_a_tampered_user_is_rejected() -> None:
  state = signing.issue_state(5432, 12345, SECRET, NOW)
  forged = signing.sign({'kind': 'state', 'user_id': 1, 'company_id': 12345, 'exp': NOW + 60}, 'x')
  body, _, mac = state.partition('.')
  forged_body, _, _ = forged.partition('.')

  assert signing.verify_state(f'{forged_body}.{mac}', SECRET, NOW) is None
  assert signing.verify_state(f'{body}.', SECRET, NOW) is None
  assert signing.verify_state('not-a-signed-value', SECRET, NOW) is None
  assert signing.verify_state('', SECRET, NOW) is None


def test_a_cookie_is_not_accepted_as_state_and_a_state_is_not_accepted_as_a_cookie() -> None:
  cookie = signing.issue_cookie(5432, 12345, SECRET, NOW)
  state = signing.issue_state(5432, 12345, SECRET, NOW)

  assert signing.verify_state(cookie, SECRET, NOW) is None
  assert not signing.cookie_is_valid(state, 5432, 12345, SECRET, NOW)


def test_cookie_is_valid_only_for_its_own_user_and_company() -> None:
  cookie = signing.issue_cookie(5432, 12345, SECRET, NOW)

  assert signing.cookie_is_valid(cookie, 5432, 12345, SECRET, NOW)
  assert not signing.cookie_is_valid(cookie, 9999, 12345, SECRET, NOW)
  assert not signing.cookie_is_valid(cookie, 5432, 9999, SECRET, NOW)


def test_cookie_that_is_missing_forged_or_older_than_its_max_age_is_not_valid() -> None:
  cookie = signing.issue_cookie(5432, 12345, SECRET, NOW)

  assert not signing.cookie_is_valid(None, 5432, 12345, SECRET, NOW)
  assert not signing.cookie_is_valid('', 5432, 12345, SECRET, NOW)
  assert not signing.cookie_is_valid(cookie + 'x', 5432, 12345, SECRET, NOW)
  assert not signing.cookie_is_valid(cookie, 5432, 12345, 'other', NOW)
  assert signing.cookie_is_valid(cookie, 5432, 12345, SECRET, NOW + COOKIE_MAX_AGE_SECONDS)
  assert not signing.cookie_is_valid(cookie, 5432, 12345, SECRET, NOW + COOKIE_MAX_AGE_SECONDS + 1)
