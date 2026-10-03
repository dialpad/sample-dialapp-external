import { describe, expect, it } from 'vitest';

import { acmeFields } from './acme';

describe('acmeFields', () => {
  it('prefixes strings, Acmes lists element by element, and leaves other values unchanged', () => {
    const fields = acmeFields({
      displayName: 'Pat Customer',
      phones: ['+1 555 0199', '+1 555 0100'],
      extension: 42,
      recorded: true,
    });

    expect(fields).toEqual([
      { label: 'displayName', value: 'Acme Pat Customer' },
      { label: 'phones', value: 'Acme +1 555 0199, Acme +1 555 0100' },
      { label: 'extension', value: '42' },
      { label: 'recorded', value: 'true' },
    ]);
  });

  it('omits null, undefined, empty-string and empty-list fields but keeps zero and false', () => {
    const fields = acmeFields({
      firstName: null,
      lastName: undefined,
      jobTitle: '',
      emails: [],
      extension: 0,
      recorded: false,
    });

    expect(fields.map((f) => f.label)).toEqual(['extension', 'recorded']);
  });
});
