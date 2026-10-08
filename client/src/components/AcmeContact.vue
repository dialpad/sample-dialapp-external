<script setup lang="ts">
// The contact Dialpad sent, with every field "Acme'd": the reference app has no CRM, so this
// proves data flows from the host to the iframe panel. Fields are labelled by the SDK's field names.
//
// `contact` is null until Dialpad sends one (the SDK's `state.contact`), and a different contact
// arrives in a new iframe, so the iframe panel simply re-renders. Empty fields are left out.
//
// It is used twice when a call is active: for the iframe panel's contact and, if that is a different
// person, for the call's own contact. `title` and `testId` tell the two apart.
import type { Contact } from '@dialpad/dialapp-external-sdk';
import { computed, useId } from 'vue';

import { acmeFields } from '../acme';

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

/** The rows to show; empty when no contact is open, which shows a short "no contact" line. */
const fields = computed(() => (props.contact ? acmeFields(props.contact) : []));
</script>

<template>
  <section :aria-labelledby="headingId" :data-testid="testId">
    <h2 :id="headingId" class="acme-heading">{{ title }}</h2>
    <p v-if="fields.length === 0" class="acme-muted">No contact is open.</p>
    <dl v-else class="acme-fields">
      <template v-for="field in fields" :key="field.label">
        <dt>{{ field.label }}</dt>
        <dd>{{ field.value }}</dd>
      </template>
    </dl>
  </section>
</template>

<style scoped>
.acme-fields {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--dt-space-200) var(--dt-space-400);
  margin: 0;
}
.acme-fields dt {
  color: var(--dt-color-foreground-secondary);
}
.acme-fields dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
