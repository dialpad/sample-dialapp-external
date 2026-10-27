"""The signed state (acme_dialpad_rightbar/signing.py) and storage cookie (demo/fake_storage.py).

Covers forged, expired, wrong-purpose and wrong-user values: what the OAuth callback and the
connection checks rely on to trust a ``state`` or a storage cookie.
"""

from dataclasses import replace

from acme_dialpad_rightbar import signing
from acme_dialpad_rightbar.connect import state as oauth_state
from acme_dialpad_rightbar.connect.state import STATE_TTL_SECONDS
from acme_dialpad_rightbar.demo import fake_storage
from acme_dialpad_rightbar.demo.fake_storage import COOKIE_MAX_AGE_SECONDS

SECRET = 'app-secret'
NOW = 1_000_000.0


def test_a_state_is_valid_for_the_user_it_was_issued_for_until_ten_minutes_pass() -> None:
  state = oauth_state.issue_state(5432, 12345, SECRET, NOW)

  claims = oauth_state.verify_state(state, SECRET, NOW + STATE_TTL_SECONDS - 1)

  assert claims is not None
  assert (claims.user_id, claims.company_id) == (5432, 12345)
  assert oauth_state.verify_state(state, SECRET, NOW + STATE_TTL_SECONDS) is None


def test_a_forged_or_malformed_state_is_rejected() -> None:
  state = oauth_state.issue_state(5432, 12345, SECRET, NOW)
  tampered = signing.sign({
      'kind': 'state',
      'user_id': 1,
      'company_id': 12345,
      'exp': NOW + 60
  }, 'x')
  body, _, mac = state.partition('.')
  tampered_body, _, _ = tampered.partition('.')

  assert oauth_state.verify_state(oauth_state.issue_state(5432, 12345, 'other-secret', NOW), SECRET,
                                  NOW) is None
  assert oauth_state.verify_state(f'{tampered_body}.{mac}', SECRET, NOW) is None
  assert oauth_state.verify_state(f'{body}.', SECRET, NOW) is None
  assert oauth_state.verify_state('not-a-signed-value', SECRET, NOW) is None
  assert oauth_state.verify_state('', SECRET, NOW) is None


def some_claims(**overrides: object) -> fake_storage.CookieClaims:
  """Return connected cookie claims for Jane, with any field overridden."""
  jane = fake_storage.CookieClaims(user_id=5432,
                                   company_id=12345,
                                   token='an-access-token',
                                   connected=True)
  return replace(jane, **overrides)


def test_a_storage_cookie_is_not_accepted_as_state_and_a_state_is_not_accepted_as_a_cookie(
) -> None:
  cookie = fake_storage.issue_cookie(some_claims(), SECRET, NOW)
  state = oauth_state.issue_state(5432, 12345, SECRET, NOW)

  assert oauth_state.verify_state(cookie, SECRET, NOW) is None
  assert fake_storage.read_cookie(state, SECRET, NOW) is None


def test_a_cookie_round_trips_its_user_token_and_connection() -> None:
  for connected in (True, False):
    cookie = fake_storage.issue_cookie(some_claims(connected=connected), SECRET, NOW)

    assert fake_storage.read_cookie(cookie, SECRET, NOW + 1) == some_claims(connected=connected)


def test_new_access_tokens_are_random_and_long_enough() -> None:
  tokens = {signing.new_access_token() for _ in range(50)}

  assert len(tokens) == 50
  assert all(len(token) >= 40 for token in tokens)


def test_a_cookie_that_is_missing_forged_or_older_than_its_max_age_is_not_read() -> None:
  cookie = fake_storage.issue_cookie(some_claims(), SECRET, NOW)

  assert fake_storage.read_cookie(None, SECRET, NOW) is None
  assert fake_storage.read_cookie('', SECRET, NOW) is None
  assert fake_storage.read_cookie(cookie + 'x', SECRET, NOW) is None
  assert fake_storage.read_cookie(cookie, 'other', NOW) is None
  assert fake_storage.read_cookie(cookie, SECRET, NOW + COOKIE_MAX_AGE_SECONDS) is not None
  assert fake_storage.read_cookie(cookie, SECRET, NOW + COOKIE_MAX_AGE_SECONDS + 1) is None


def test_a_signed_cookie_with_missing_or_mistyped_fields_is_not_read() -> None:
  whole: dict[str, object] = {
      'kind': 'session',
      'user_id': 5432,
      'company_id': 12345,
      'token': 'a-token',
      'connected': True,
      'iat': NOW,
  }

  assert fake_storage.read_cookie(signing.sign(whole, SECRET), SECRET, NOW) is not None
  for broken in (
      {
          'token': ''
      },
      {
          'token': 7
      },
      {
          'connected': 'yes'
      },
      {
          'user_id': '5432'
      },
      {
          'iat': 'now'
      },
  ):
    value = signing.sign({**whole, **broken}, SECRET)
    assert fake_storage.read_cookie(value, SECRET, NOW) is None
  for missing in ('token', 'connected', 'user_id', 'company_id', 'iat'):
    payload = {key: value for key, value in whole.items() if key != missing}
    assert fake_storage.read_cookie(signing.sign(payload, SECRET), SECRET, NOW) is None
