<script setup lang="ts">
// Connected: who you are (the host's `get/user`), the active call, and the contact Dialpad sent,
// Acme'd, plus the OAuth scopes the connection has. All of it comes from the SDK's snapshot, which
// keeps the call and contact up to date; connecting doesn't reset them.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';

import AcmeContact from './AcmeContact.vue';
import CallCard from './CallCard.vue';
import DisconnectButton from './DisconnectButton.vue';
import UserCard from './UserCard.vue';

const { state } = useRightbar();
</script>

<template>
  <div class="acme-connected" data-testid="connected-view">
    <UserCard :user="state.user" />
    <CallCard :call="state.call" />
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

<style scoped>
.acme-connected {
  display: flex;
  flex-direction: column;
  gap: var(--dt-space-500);
}
</style>
