<script setup lang="ts">
// The CRM's view of the contact Dialpad sent. Dialpad's contact is Dialpad's own (a name, phones,
// emails); a partner's panel exists to show the partner's record for that person. Getting from one
// to the other is the "contact mapping", and it needs the user's CRM credentials, so it happens on
// the server: this component sends the contact to `POST /api/contact` (see `contactApi.ts`) and
// shows the fields that come back.
//
// What the demo does: the reference app has no CRM, so the server answers with every field "Acme'd"
// (text prefixed with `Acme `), which proves the contact went to the server and back as the right
// user, and with its fake record page as the record. What a real app does: the server maps the
// contact to a CRM record with the user's stored CRM token, fetches it and returns its fields and
// its URL in the CRM. Either way, this component then calls the SDK's `linkRecord(...)` with the
// record, so Dialpad shows a "View <type>" header button for it and uses it for screen pops.
//
// `contact` is null until Dialpad sends one (the SDK's `state.contact`). Each new contact is looked
// up again, and the answer to an older contact that arrives late is ignored. The record is unlinked
// as soon as the contact changes, when the lookup fails, and when the section goes away (on
// disconnect), so Dialpad never shows a record for another contact.
//
// It is used twice when a call is active: for the iframe panel's contact and, if that is a different
// person, for the call's own contact. `title` and `testId` tell the two apart, and only the panel's
// own contact sets `link`: Dialpad keeps one linked record per panel.
import type { Contact, LinkedRecord } from '@dialpad/dialapp-external-sdk';
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { onBeforeUnmount, ref, useId, watch } from 'vue';

import { type AcmeField, fetchAcmeContact } from '../contactApi';

const { showToast, linkRecord } = useRightbar();

const props = withDefaults(
  defineProps<{
    contact: Contact | null;
    /** The section's heading. */
    title?: string;
    /** The section's `data-testid`, so tests can tell the two uses apart. */
    testId?: string;
    /** Whether to link the contact's record in Dialpad; only for the panel's own contact. */
    link?: boolean;
  }>(),
  { title: "This contact, Acme'd", testId: 'acme-contact', link: false },
);

/** Whether this section has a record linked in Dialpad, so it unlinks only what it linked. */
let linked = false;

/**
 * Link `record` in Dialpad, or unlink with `null`. Nothing happens without `link`, or when unlinking
 * with nothing linked. Best effort: a host that rejects it must not break the panel; it is logged.
 */
function setLinkedRecord(record: LinkedRecord | null): void {
  if (!props.link || (record === null && !linked)) {
    return;
  }
  linked = record !== null;
  linkRecord(record).catch((error: unknown) => {
    console.warn("Dialpad didn't link the record", error);
  });
}

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
    setLinkedRecord(null);
    if (!contact) {
      status.value = 'idle';
      return;
    }
    status.value = 'loading';
    try {
      const answer = await fetchAcmeContact(contact);
      if (mine === lookup) {
        fields.value = answer.fields;
        status.value = 'ready';
        setLinkedRecord(answer.record);
      }
    } catch (error) {
      if (mine === lookup) {
        status.value = 'failed';
        console.warn('The contact lookup failed', error);
        // Besides the message in the panel, tell the user in Dialpad. Best effort: a host that
        // rejects the toast must not break the panel; it is logged and the panel goes on.
        showToast({
          text: "Couldn't load the contact from Acme CRM",
          type: 'error',
        }).catch((toastError: unknown) => {
          console.warn("Dialpad didn't show the toast", toastError);
        });
      }
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  // A lookup still waiting for the server is now stale, so its answer can't link a record after the
  // section is gone.
  lookup += 1;
  setLinkedRecord(null);
});
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
