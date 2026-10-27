<script setup lang="ts">
// The iframe panel's root: a title, a "reload" notice if the access token was rejected, and then either
// the connected view or the Connect gate, switched by the SDK's `connection.connected`. Mounted by
// `bootstrap` once the SDK has started, so `useRightbar()` always has a snapshot to read.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { computed, watch } from 'vue';

import { accessTokenRejected } from './api';
import ConnectedView from './ConnectedView.vue';
import ConnectGate from './connect/ConnectGate.vue';

const { state, showToast } = useRightbar();
const connected = computed(() => state.value.connection.connected);

// Tell the user in Dialpad, outside the panel, when the connection changes. One watcher covers every
// way it changes: Connect finishing, the panel's Disconnect button and Dialpad's own panel menu all
// end here. Opening the panel already connected is not a change, so it shows nothing. A toast is a
// courtesy, so a host that rejects it must not break the panel; it is logged and the panel goes on.
watch(connected, (isConnected) => {
  const toast = isConnected
    ? { text: 'Connected to Acme CRM', type: 'success' as const }
    : { text: 'Disconnected from Acme CRM', type: 'info' as const };
  showToast(toast).catch((error: unknown) => {
    console.warn("Dialpad didn't show the toast", error);
  });
});
</script>

<template>
  <h1 class="acme-title">Acme for Dialpad (demo)</h1>
  <DtNotice
    v-if="accessTokenRejected"
    kind="warning"
    :show-close="false"
    role="alert"
  >
    Reload the panel to keep going.
  </DtNotice>
  <ConnectedView v-if="connected" />
  <ConnectGate v-else />
</template>
