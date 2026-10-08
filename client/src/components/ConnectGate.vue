<script setup lang="ts">
// The Connect gate: what the iframe panel shows while the user is not connected. It is the UI the SDK
// deliberately doesn't ship, so partners copy this file and change the copy.
//
// It renders from the SDK's `connection` state and has four looks:
//   * not connected: a Connect button;
//   * connecting: Connect was clicked, Dialpad opened the authorize URL in a popup (or the desktop
//     app's login window) and the SDK is polling `/dialpad/ext-connection`. The button is disabled
//     and the text says to finish in the Acme window. This ends by itself when the server says
//     "connected" (the gate disappears), or after 2 minutes with a timeout;
//   * failed: `timeout` (polling gave up), `network` or `request_failed` (a connection check
//     failed), each with an explanation and "Try again".
//
// With one OAuth client `authorize()` needs no argument. A company with several would have
// several `authorizationUrls`, and this is where the user would pick one.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtButton } from '@dialpad/dialtone/vue/lib/button';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { computed } from 'vue';

const { state, authorize } = useRightbar();

const connection = computed(() => state.value.connection);

/** What the user is told for each way a connection check can fail, keyed by the SDK's error code. */
const ERROR_COPY: Record<string, string> = {
  timeout: "Acme didn't respond in time.",
  network: "We couldn't reach Acme. Check your connection.",
  request_failed: 'Something went wrong while checking your Acme connection.',
};

/** The message for the current error, or null when there is none (so no notice and "Connect"). */
const errorCopy = computed(() => {
  const code = connection.value.error?.code;
  return code ? ERROR_COPY[code] : null;
});
</script>

<template>
  <section class="acme-gate" data-testid="connect-gate">
    <p v-if="connection.pending" role="status">
      Waiting for you to finish connecting in the Acme window…
    </p>
    <template v-else>
      <p>Connect your Acme account to see your contacts here.</p>
      <DtNotice
        v-if="errorCopy"
        kind="critical"
        :show-close="false"
        role="alert"
      >
        {{ errorCopy }}
      </DtNotice>
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
