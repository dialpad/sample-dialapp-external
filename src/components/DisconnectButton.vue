<script setup lang="ts">
// Disconnect with an inline confirmation: the button becomes a short confirmation row, never a
// modal, because the panel's iframe is about 300px wide and overlays can't leave it.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { DtButton } from '@dialpad/dialtone/vue/lib/button';
import { DtNotice } from '@dialpad/dialtone/vue/lib/notice';
import { ref } from 'vue';

const { state, disconnect } = useRightbar();
const confirming = ref(false);

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

<style scoped>
.acme-disconnect {
  display: flex;
  gap: var(--dt-space-300);
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
