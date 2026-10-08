<script setup lang="ts">
// The CRM's view of the contact Dialpad sent. Dialpad's contact is Dialpad's own (a name, phones,
// emails); a partner's panel exists to show the partner's record for that person. Getting from one
// to the other is the "contact mapping", and it needs the user's CRM credentials, so it happens on
// the server: this component sends the contact to `POST /api/contact` (see `contactApi.ts`) and
// shows the fields that come back.
//
// What the demo does: the reference app has no CRM, so the server answers with every field "Acme'd"
// (text prefixed with `Acme `), which proves the contact went to the server and back as the right
// user. What a real app does: the server maps the contact to a CRM record with the user's stored
// CRM token, fetches it and returns its fields; then this component calls the SDK's
// `linkRecord(...)` with the record's URL so Dialpad can offer "View record" and screen-pop it.
//
// `contact` is null until Dialpad sends one (the SDK's `state.contact`). Each new contact is looked
// up again, and the answer to an older contact that arrives late is ignored.
//
// It is used twice when a call is active: for the iframe panel's contact and, if that is a different
// person, for the call's own contact. `title` and `testId` tell the two apart.
import type { Contact } from '@dialpad/dialapp-external-sdk';
import { ref, useId, watch } from 'vue';

import { type AcmeField, fetchAcmeFields } from '../contactApi';

const props = withDefaults(
  defineProps<{
    contact: Contact | null;
    /** The section's heading. */
    title?: string;
    /** The section's `data-testid`, so tests can tell the two uses apart. */
    testId?: string;
  }>(),
  { title: "This contact, Acme'd", testId: 'acme-contact' },
);

/** An id for the heading that is unique per instance, since two sections can be on screen. */
const headingId = useId();

/** Where the lookup stands: no contact, waiting for the server, answered, or failed. */
const status = ref<'idle' | 'loading' | 'ready' | 'failed'>('idle');
/** The rows the server answered with for the current contact. */
const fields = ref<AcmeField[]>([]);
/** Counts lookups, so the answer to an older contact is recognised as stale and dropped. */
let lookup = 0;

watch(
  () => props.contact,
  async (contact) => {
    lookup += 1;
    const mine = lookup;
    fields.value = [];
    if (!contact) {
      status.value = 'idle';
      return;
    }
    status.value = 'loading';
    try {
      const rows = await fetchAcmeFields(contact);
      if (mine === lookup) {
        fields.value = rows;
        status.value = 'ready';
      }
    } catch {
      if (mine === lookup) {
        status.value = 'failed';
      }
    }
  },
  { immediate: true },
);
</script>

<template>
  <section
    class="acme-contact"
    :aria-labelledby="headingId"
    :data-testid="testId"
  >
    <h2 :id="headingId" class="acme-heading">{{ title }}</h2>
    <p v-if="status === 'idle'" class="acme-muted">No contact is open.</p>
    <p v-else-if="status === 'loading'" class="acme-muted" role="status">
      Loading the contact...
    </p>
    <p v-else-if="status === 'failed'" class="acme-muted" role="alert">
      Couldn't load the contact. Try again in a moment.
    </p>
    <p v-else-if="fields.length === 0" class="acme-muted">
      There are no details for this contact.
    </p>
    <dl v-else class="acme-contact__fields">
      <template v-for="field in fields" :key="field.label">
        <dt class="acme-contact__label">{{ field.label }}</dt>
        <dd class="acme-contact__value">{{ field.value }}</dd>
      </template>
    </dl>
  </section>
</template>

<style>
.acme-contact__fields {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--dt-space-200) var(--dt-space-400);
  margin: 0;
}
.acme-contact__label {
  color: var(--dt-color-foreground-secondary);
}
.acme-contact__value {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
