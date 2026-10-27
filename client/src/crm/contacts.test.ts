import { makeContact } from '@dialpad/dialapp-external-sdk/testing';
import { describe, expect, it } from 'vitest';

import { isSameContact } from './contacts';

describe('isSameContact', () => {
  it('is false when either contact is missing', () => {
    expect(isSameContact(null, makeContact())).toBe(false);
    expect(isSameContact(makeContact(), null)).toBe(false);
    expect(isSameContact(null, null)).toBe(false);
  });

  it('compares ids when both contacts have one, whatever else differs', () => {
    const pat = makeContact({ id: '1', displayName: 'Pat' });

    expect(
      isSameContact(pat, makeContact({ id: '1', displayName: 'Other' })),
    ).toBe(true);
    expect(
      isSameContact(pat, makeContact({ id: '2', displayName: 'Pat' })),
    ).toBe(false);
  });

  it('falls back to name, phone and email when an id is missing', () => {
    const pat = makeContact({
      id: null,
      displayName: 'Pat',
      primaryPhone: '1',
      primaryEmail: 'p@x',
    });

    expect(
      isSameContact(
        pat,
        makeContact({
          id: '9',
          displayName: 'Pat',
          primaryPhone: '1',
          primaryEmail: 'p@x',
        }),
      ),
    ).toBe(true);
    expect(
      isSameContact(
        pat,
        makeContact({
          id: '9',
          displayName: 'Pat',
          primaryPhone: '2',
          primaryEmail: 'p@x',
        }),
      ),
    ).toBe(false);
  });
});
