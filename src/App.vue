<script setup lang="ts">
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { computed } from 'vue';

import { sessionExpired } from './api';
import ConnectedView from './components/ConnectedView.vue';
import ConnectGate from './components/ConnectGate.vue';

const { state } = useRightbar();
const connected = computed(() => state.value.connection.connected);
</script>

<template>
  <h1 class="acme-title">Acme CRM (demo)</h1>
  <DtNotice
    v-if="sessionExpired"
    kind="warning"
    :show-close="false"
    role="alert"
  >
    Reload the panel to keep going.
  </DtNotice>
  <ConnectedView v-if="connected" />
  <ConnectGate v-else />
</template>
