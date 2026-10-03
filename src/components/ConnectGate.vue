<script setup lang="ts">
// The Connect gate: the UI the SDK deliberately doesn't ship. Partners copy this file and change
// the copy. It renders `connection` from the SDK's snapshot: not connected, connecting (polling),
// and the three failures (`timeout`, `network`, `request_failed`), each with "Try again".
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtButton } from '@dialpad/dialtone/vue/lib/button';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { computed } from 'vue';

const { state, authorize } = useRightbar();

const connection = computed(() => state.value.connection);

const ERROR_COPY: Record<string, string> = {
  timeout: "Acme didn't respond in time.",
  network: "We couldn't reach Acme. Check your connection.",
  request_failed: 'Something went wrong while checking your Acme connection.',
};

const errorCopy = computed(() => {
  const code = connection.value.error?.code;
  return code ? ERROR_COPY[code] : null;
});
</script>

<template>
  <section class="acme-gate" data-testid="connect-gate">
    <p v-if="connection.pending" role="status">Waiting for you to finish connecting in the Acme window…</p>
    <template v-else>
      <p>Connect your Acme account to see your contacts here.</p>
      <DtNotice v-if="errorCopy" kind="error" :title="errorCopy" role="alert" />
    </template>
    <DtButton
      :disabled="connection.pending"
      data-testid="connect-button"
      @click="authorize()"
    >
      {{ errorCopy ? 'Try again' : 'Connect' }}
    </DtButton>
  </section>
</template>

<style scoped>
.acme-gate {
  display: flex;
  flex-direction: column;
  gap: var(--dt-space-400);
  align-items: center;
  text-align: center;
}
</style>
