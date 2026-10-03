<script setup lang="ts">
// Connected: who you are (the idtoken's claims, from the page data) and the contact Dialpad sent,
// Acme'd. Both come from the SDK's snapshot.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';

import AcmeContact from './AcmeContact.vue';
import ClaimsCard from './ClaimsCard.vue';
import DisconnectButton from './DisconnectButton.vue';

const { state } = useRightbar();
</script>

<template>
  <div class="acme-connected" data-testid="connected-view">
    <ClaimsCard :user="state.user" />
    <AcmeContact :contact="state.contact" />
    <DisconnectButton />
  </div>
</template>

<style scoped>
.acme-connected {
  display: flex;
  flex-direction: column;
  gap: var(--dt-space-500);
}
</style>
