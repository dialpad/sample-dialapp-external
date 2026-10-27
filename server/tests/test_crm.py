"""The CRM record's routes (``acme_dialpad_rightbar.crm``): the contact route and the record page.

An app that doesn't show a CRM record deletes this file with ``acme_dialpad_rightbar/crm/``.
"""

from typing import TYPE_CHECKING

import pytest

from tests.conftest import Env
from tests.conftest import Panel
from tests.conftest import connect
from tests.conftest import json_of

if TYPE_CHECKING:
  from httpx import Response

# --- the example route the iframe panel adds for itself ------------------------------------------

CONTACT = {
    'id': '4800000000000001',
    'displayName': 'Pat Customer',
    'firstName': None,
    'phones': ['+1 555 0199'],
    'emails': [],
}


async def post_contact(env: Env, panel: Panel, body: object) -> Response:
  """POST ``body`` as JSON to the contact route, as the panel does."""
  return await env.post('/api/contact', headers=panel.headers, json=body)


async def test_the_contact_route_acmes_text_and_lists_shows_other_values_as_json_and_drops_empties(
    env: Env,) -> None:
  panel = await env.open_panel()
  await connect(env, panel)
  contact = {
      'id': '4800000000000001',
      'displayName': 'Pat Customer',
      'phones': ['+1 555 0199', '+1 555 0100'],
      'extension': 42,
      'recorded': True,
      'ratio': 1.5,
      'zero': 0,
      'no': False,
      'custom': {
          'tier': 'gold'
      },
      'tags': ['vip', None],
      'firstName': None,
      'jobTitle': '',
      'emails': [],
  }

  response = await post_contact(env, panel, {'contact': contact})

  assert response.status_code == 200
  assert 'set-cookie' not in response.headers
  body = json_of(response)
  assert list(body) == ['fields', 'record']
  assert body['record'] == {
      'type': 'Contact',
      'url': f'{env.settings.base_url}/records/4800000000000001',
  }
  assert [(row['label'], row['value']) for row in body['fields']] == [
      ('id', 'Acme 4800000000000001'),
      ('displayName', 'Acme Pat Customer'),
      ('phones', 'Acme +1 555 0199, Acme +1 555 0100'),
      ('extension', '42'),
      ('recorded', 'true'),
      ('ratio', '1.5'),
      ('zero', '0'),
      ('no', 'false'),
      ('custom', '{"tier": "gold"}'),
      ('tags', 'Acme vip, null'),
  ]


@pytest.mark.parametrize(
    ('contact_id', 'record_path'),
    [
        ('a/b?c', '/records/a%2Fb%3Fc'),
        (None, None),
        (42, None),
    ],
    ids=['an id that needs quoting', 'no id', 'an id that is not text'],
)
async def test_the_record_link_quotes_the_contact_id_and_is_null_without_one(
    env: Env, contact_id: object, record_path: str | None) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  response = await post_contact(env, panel, {'contact': {**CONTACT, 'id': contact_id}})

  record = json_of(response)['record']
  if record_path is None:
    assert record is None
  else:
    assert record == {'type': 'Contact', 'url': f'{env.settings.base_url}{record_path}'}


async def test_a_user_who_has_not_connected_gets_403_not_a_lookup(env: Env) -> None:
  panel = await env.open_panel()

  response = await post_contact(env, panel, {'contact': CONTACT})

  assert response.status_code == 403
  assert json_of(response)['code'] == 'not_connected'
  assert 'Acme' not in response.text.replace('Acme account', '')


@pytest.mark.parametrize(
    'request_kwargs',
    [
        {
            'json': []
        },
        {
            'json': {}
        },
        {
            'json': {
                'contact': 'Pat'
            }
        },
        {},
        {
            'content': b'{not json'
        },
    ],
    ids=['array', 'no contact key', 'contact is not an object', 'empty body', 'not json'],
)
async def test_a_body_that_is_not_a_contact_object_gets_400(
    env: Env, request_kwargs: dict[str, object]) -> None:
  panel = await env.open_panel()
  await connect(env, panel)

  response = await env.post('/api/contact', headers=panel.headers, **request_kwargs)

  assert response.status_code == 400
  assert json_of(response)['code'] == 'invalid_request'


# --- the fake CRM record page ------------------------------------------------------------------


async def test_the_record_page_is_labelled_fake_shows_the_id_escaped_and_is_locked_down(
    env: Env) -> None:
  # The id arrives percent-encoded, as `record_url` builds it, and includes an encoded slash.
  response = await env.get('/records/%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E')

  assert response.status_code == 200
  assert response.headers['content-type'].startswith('text/html')
  assert 'fake CRM record (demo only)' in response.text
  assert '<code>&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</code>' in response.text
  assert '<script>' not in response.text
  assert 'set-cookie' not in response.headers
  csp = response.headers['content-security-policy']
  nonce = csp.split("style-src 'nonce-")[1].split("'")[0]
  assert "default-src 'none'" in csp
  assert "frame-ancestors 'none'" in csp
  assert f'<style nonce="{nonce}">' in response.text
  assert response.headers['referrer-policy'] == 'no-referrer'
  assert response.headers['cache-control'] == 'no-store'
