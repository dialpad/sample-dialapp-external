"""The per-user state kept in the session cookie (acme_crm/state.py)."""

from acme_crm.signing import COOKIE_MAX_AGE_SECONDS
from acme_crm.state import CookieBackedDatabaseStorage
from acme_crm.stores import UserKey

SECRET = 'app-secret'
NOW = 1_000_000.0
JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_a_new_state_has_a_fresh_access_token_and_is_not_connected() -> None:
  first = CookieBackedDatabaseStorage.new(JANE)
  second = CookieBackedDatabaseStorage.new(JANE)

  assert first.user_key() == JANE
  assert first.is_external_connected() is False
  assert len(first.get_access_token()) >= 40
  assert first.get_access_token() != second.get_access_token()


def test_a_state_survives_the_cookie_round_trip() -> None:
  state = CookieBackedDatabaseStorage.new(JANE).with_external_connected(connected=True)

  read = CookieBackedDatabaseStorage.from_cookie(state.to_cookie(SECRET, NOW), SECRET, NOW + 1)

  assert read is not None
  assert read.user_key() == JANE
  assert read.get_access_token() == state.get_access_token()
  assert read.is_external_connected() is True


def test_changing_the_connection_keeps_the_token_and_leaves_the_original_unchanged() -> None:
  state = CookieBackedDatabaseStorage.new(JANE)

  connected = state.with_external_connected(connected=True)
  disconnected = connected.with_external_connected(connected=False)

  assert connected.is_external_connected() is True
  assert state.is_external_connected() is False
  assert disconnected.is_external_connected() is False
  assert {state.get_access_token(),
          connected.get_access_token(),
          disconnected.get_access_token()} == {state.get_access_token()}


def test_a_cookie_that_is_missing_forged_or_expired_gives_no_state() -> None:
  cookie = CookieBackedDatabaseStorage.new(JANE).to_cookie(SECRET, NOW)

  assert CookieBackedDatabaseStorage.from_cookie(None, SECRET, NOW) is None
  assert CookieBackedDatabaseStorage.from_cookie('', SECRET, NOW) is None
  assert CookieBackedDatabaseStorage.from_cookie(cookie, 'another-secret', NOW) is None
  assert CookieBackedDatabaseStorage.from_cookie(cookie + 'x', SECRET, NOW) is None
  assert CookieBackedDatabaseStorage.from_cookie(cookie, SECRET, NOW + COOKIE_MAX_AGE_SECONDS)
  assert CookieBackedDatabaseStorage.from_cookie(cookie, SECRET,
                                                 NOW + COOKIE_MAX_AGE_SECONDS + 1) is None


def test_a_state_belongs_only_to_its_own_user_and_company() -> None:
  state = CookieBackedDatabaseStorage.new(JANE)

  assert state.belongs_to(JANE)
  assert not state.belongs_to(PAT)
  assert not state.belongs_to(UserKey(company_id=99, user_id=JANE.user_id))


def test_only_the_states_own_access_token_matches() -> None:
  state = CookieBackedDatabaseStorage.new(JANE)
  other = CookieBackedDatabaseStorage.new(JANE)

  assert state.has_access_token(state.get_access_token())
  assert not state.has_access_token(other.get_access_token())
  assert not state.has_access_token('')
