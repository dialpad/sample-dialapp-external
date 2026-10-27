<script setup lang="ts">
// The CRM record of the contact Dialpad sent, Acme'd. `ConnectedView.vue` shows it.
//
// During a call there can be two contacts: the iframe panel's (`state.contact`) and the call's own
// (`state.call.contact`). Usually they are the same person, because Dialpad opens the caller's
// contact in the right bar, and then one section is enough. When they differ, both are shown, and
// only the panel's own contact is linked in Dialpad.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { computed } from 'vue';

import AcmeContact from './AcmeContact.vue';
import { isSameContact } from './contacts';

const { state } = useRightbar();

/** The call's contact when there is one and it is not the iframe panel's contact; otherwise null. */
const otherCallContact = computed(() => {
  const callContact = state.value.call?.contact ?? null;
  return isSameContact(callContact, state.value.contact) ? null : callContact;
});
</script>

<template>
  <AcmeContact
    v-if="otherCallContact"
    :contact="otherCallContact"
    title="Call contact, Acme'd"
    test-id="call-contact"
  />
  <AcmeContact :contact="state.contact" link />
</template>
