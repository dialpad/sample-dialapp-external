<script setup lang="ts">
// Disconnect with an inline confirmation: the button becomes a short confirmation row, never a
// modal, because the iframe panel is about 300px wide and overlays can't leave it.
//
// Clicking Disconnect only asks "Disconnect Acme?"; Cancel goes back. Confirming calls the SDK's
// `disconnect()`, which calls `/dialpad/ext-disconnect` and tells Dialpad the iframe panel is no longer
// connected, after which `App.vue` swaps this whole view for the Connect gate. If the call fails
// the user stays connected and sees an error here. Disconnecting from Dialpad's own iframe panel menu
// takes the same path inside the SDK, without this confirmation.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtButton } from '@dialpad/dialtone/vue/lib/button';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { ref } from 'vue';

const { state, disconnect } = useRightbar();
/** Whether the confirmation row is showing instead of the Disconnect button. */
const confirming = ref(false);

/**
 * Carry out the confirmed disconnect.
 *
 * The row closes first; when the SDK finishes, `connection.connected` is false and this component
 * is unmounted with its parent. If it failed, `connection.error` is set and the user is still
 * connected, so the button is back with an error above it.
 */
async function confirm(): Promise<void> {
  confirming.value = false;
  await disconnect();
}
</script>

<template>
  <DtNotice
    v-if="state.connection.error"
    kind="critical"
    :show-close="false"
    role="alert"
  >
    We couldn't disconnect Acme. Try again.
  </DtNotice>
  <div class="acme-disconnect">
    <template v-if="confirming">
      <span id="disconnect-prompt">Disconnect Acme?</span>
      <DtButton importance="outlined" size="sm" @click="confirming = false">
        Cancel
      </DtButton>
      <DtButton
        kind="critical"
        size="sm"
        aria-describedby="disconnect-prompt"
        data-testid="disconnect-confirm"
        @click="confirm"
      >
        Disconnect
      </DtButton>
    </template>
    <DtButton
      v-else
      importance="outlined"
      size="sm"
      data-testid="disconnect-button"
      @click="confirming = true"
    >
      Disconnect
    </DtButton>
  </div>
</template>

<style>
.acme-disconnect {
  display: flex;
  gap: var(--dt-space-300);
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
