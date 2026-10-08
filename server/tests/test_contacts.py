"""The demo's stand-in for a CRM contact lookup (acme_crm/contacts.py)."""

from acme_crm.contacts import AcmeField
from acme_crm.contacts import acme_fields


def test_text_gets_the_prefix_lists_are_acmed_by_element_and_other_values_are_shown_as_json(
) -> None:
  fields = acme_fields({
      'displayName': 'Pat Customer',
      'phones': ['+1 555 0199', '+1 555 0100'],
      'extension': 42,
      'recorded': True,
      'ratio': 1.5,
  })

  assert fields == [
      AcmeField('displayName', 'Acme Pat Customer'),
      AcmeField('phones', 'Acme +1 555 0199, Acme +1 555 0100'),
      AcmeField('extension', '42'),
      AcmeField('recorded', 'true'),
      AcmeField('ratio', '1.5'),
  ]


def test_empty_fields_are_left_out_but_zero_and_false_are_kept() -> None:
  fields = acme_fields({
      'firstName': None,
      'jobTitle': '',
      'emails': [],
      'extension': 0,
      'recorded': False,
  })

  assert [field.label for field in fields] == ['extension', 'recorded']


def test_rows_keep_the_order_of_the_contacts_fields() -> None:
  fields = acme_fields({'b': 'x', 'a': 'y', 'c': 'z'})

  assert [field.label for field in fields] == ['b', 'a', 'c']


def test_nested_values_and_nulls_inside_lists_are_shown_as_json_not_dropped() -> None:
  fields = acme_fields({'custom': {'tier': 'gold'}, 'tags': ['vip', None]})

  assert fields == [
      AcmeField('custom', '{"tier": "gold"}'),
      AcmeField('tags', 'Acme vip, null'),
  ]


def test_no_contact_fields_gives_no_rows() -> None:
  assert acme_fields({}) == []
