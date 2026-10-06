<script setup lang="ts">
// Connected: who you are (the host's `get/user`) and the contact Dialpad sent, Acme'd, plus the
// OAuth scopes the connection has. All of it comes from the SDK's snapshot.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';

import AcmeContact from './AcmeContact.vue';
import DisconnectButton from './DisconnectButton.vue';
import UserCard from './UserCard.vue';

const { state } = useRightbar();
</script>

<template>
  <div class="acme-connected" data-testid="connected-view">
    <UserCard :user="state.user" />
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
