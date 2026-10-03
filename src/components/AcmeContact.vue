<script setup lang="ts">
// The contact Dialpad sent, with every field "Acme'd": the reference app has no CRM, so this
// proves data flows from the host to the panel. Fields are labelled by the SDK's field names.
import type { Contact } from '@dialpad/dialapp-external-sdk';
import { computed } from 'vue';

import { acmeFields } from '../acme';

const props = defineProps<{ contact: Contact | null }>();

const fields = computed(() => (props.contact ? acmeFields(props.contact) : []));
</script>

<template>
  <section aria-labelledby="contact-heading" data-testid="acme-contact">
    <h2 id="contact-heading" class="acme-heading">This contact, Acme'd</h2>
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
