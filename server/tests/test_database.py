"""The per-user state kept in the session cookie (acme_dialpad_rightbar/database.py)."""

from acme_dialpad_rightbar.database import CookieBackedDatabaseStorage
from acme_dialpad_rightbar.stores import UserKey

SECRET = 'app-secret'
NOW = 1_000_000.0
JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_a_new_state_has_its_own_random_token_and_is_not_connected() -> None:
  first = CookieBackedDatabaseStorage.new(JANE)
  second = CookieBackedDatabaseStorage.new(JANE)

  assert first.user_key() == JANE
  assert first.is_external_connected() is False
  assert len(first.get_access_token()) >= 40
  assert first.get_access_token() != second.get_access_token()
  assert first.has_access_token(first.get_access_token())
  assert not first.has_access_token(second.get_access_token())
  assert not first.has_access_token('')


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


def test_a_state_belongs_only_to_its_own_user_and_company() -> None:
  state = CookieBackedDatabaseStorage.new(JANE)

  assert state.belongs_to(JANE)
  assert not state.belongs_to(PAT)
  assert not state.belongs_to(UserKey(company_id=99, user_id=JANE.user_id))
