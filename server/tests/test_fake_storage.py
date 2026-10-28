"""The stored user kept in the storage cookie (acme_dialpad_rightbar/demo/fake_storage.py)."""

from acme_dialpad_rightbar.context import UserKey
from acme_dialpad_rightbar.demo.fake_storage import StoredUser

SECRET = 'app-secret'
NOW = 1_000_000.0
JANE = UserKey(company_id=12345, user_id=5432)
PAT = UserKey(company_id=12345, user_id=777)


def test_a_new_state_has_its_own_random_token_and_is_not_connected() -> None:
  first = StoredUser.new(JANE)
  second = StoredUser.new(JANE)

  assert first.user_key() == JANE
  assert first.is_external_connected() is False
  assert len(first.get_access_token()) >= 40
  assert first.get_access_token() != second.get_access_token()
  assert first.has_access_token(first.get_access_token())
  assert not first.has_access_token(second.get_access_token())
  assert not first.has_access_token('')


def test_a_state_survives_the_cookie_round_trip() -> None:
  user = StoredUser.new(JANE).with_external_connected(connected=True)

  read = StoredUser.from_cookie(user.to_cookie(SECRET, NOW), SECRET, NOW + 1)

  assert read is not None
  assert read.user_key() == JANE
  assert read.get_access_token() == user.get_access_token()
  assert read.is_external_connected() is True


def test_changing_the_connection_keeps_the_token_and_leaves_the_original_unchanged() -> None:
  user = StoredUser.new(JANE)

  connected = user.with_external_connected(connected=True)
  disconnected = connected.with_external_connected(connected=False)

  assert connected.is_external_connected() is True
  assert user.is_external_connected() is False
  assert disconnected.is_external_connected() is False
  assert {user.get_access_token(),
          connected.get_access_token(),
          disconnected.get_access_token()} == {user.get_access_token()}


def test_a_state_belongs_only_to_its_own_user_and_company() -> None:
  user = StoredUser.new(JANE)

  assert user.belongs_to(JANE)
  assert not user.belongs_to(PAT)
  assert not user.belongs_to(UserKey(company_id=99, user_id=JANE.user_id))
