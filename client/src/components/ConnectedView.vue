<script setup lang="ts">
// Connected: who you are (the host's `get/user`), the active call, the contact Dialpad sent, Acme'd
// (`crm/CrmRecord.vue`), the server's demo call to Dialpad's API (`demo/DialpadApiCard.vue`), plus
// the OAuth scopes the connection has. All of it comes from the SDK's snapshot, which keeps the call
// and contact up to date; connecting doesn't reset them.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';

// crm-record: the next line
import CrmRecord from '../crm/CrmRecord.vue';
import DialpadApiCard from '../demo/DialpadApiCard.vue';
import CallCard from './CallCard.vue';
import DisconnectButton from './DisconnectButton.vue';
import UserCard from './UserCard.vue';

const { state } = useRightbar();
</script>

<template>
  <div class="acme-connected" data-testid="connected-view">
    <UserCard :user="state.user" />
    <DialpadApiCard />
    <CallCard :call="state.call" />
    <!-- crm-record: the next line -->
    <CrmRecord />
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
