<script setup lang="ts">
// Connected: who you are (the host's `get/user`), the active call, and the contact Dialpad sent,
// Acme'd, the server's demo call to Dialpad's API, plus the OAuth scopes the connection has. All of it comes from the SDK's snapshot, which
// keeps the call and contact up to date; connecting doesn't reset them.
//
// During a call there can be two contacts: the iframe panel's (`state.contact`) and the call's own
// (`state.call.contact`). Usually they are the same person, because Dialpad opens the caller's
// contact in the right bar, and then one section is enough. When they differ, both are shown.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { computed } from 'vue';

import { isSameContact } from '../contacts';
import AcmeContact from './AcmeContact.vue';
import CallCard from './CallCard.vue';
import DialpadApiCard from './DialpadApiCard.vue';
import DisconnectButton from './DisconnectButton.vue';
import UserCard from './UserCard.vue';

const { state } = useRightbar();

/** The call's contact when there is one and it is not the iframe panel's contact; otherwise null. */
const otherCallContact = computed(() => {
  const callContact = state.value.call?.contact ?? null;
  return isSameContact(callContact, state.value.contact) ? null : callContact;
});
</script>

<template>
  <div class="acme-connected" data-testid="connected-view">
    <UserCard :user="state.user" />
    <DialpadApiCard />
    <CallCard :call="state.call" />
    <AcmeContact
      v-if="otherCallContact"
      :contact="otherCallContact"
      title="Call contact, Acme'd"
      test-id="call-contact"
    />
    <AcmeContact :contact="state.contact" />
    <p
      v-if="state.connection.scopes.length > 0"
      class="acme-muted"
      data-testid="scopes"
    >
      Acme scopes: {{ state.connection.scopes.join(', ') }}
    </p>
    <DisconnectButton />
  </div>
</template>

<style>
.acme-connected {
  display: flex;
  flex-direction: column;
  gap: var(--dt-space-500);
}
</style>
