<script setup lang="ts">
// The active call, from the SDK's `state.call`: Dialpad sends a call when one rings and again each
// time its state changes (`ringing`, `connected`, `hangup`), so this card follows a call through to
// "Ended". `call` is null until Dialpad has sent one. A partner would use the same snapshot to
// react to calls, for example to open a record when one rings.
import type { Call } from '@dialpad/dialapp-external-sdk';
import { computed } from 'vue';

const props = defineProps<{ call: Call | null }>();

/** How each call state the host reports reads to the user; other states are shown as sent. */
const STATE_LABELS: Record<string, string> = {
  ringing: 'Ringing',
  connected: 'Connected',
  hangup: 'Ended',
};

/** The call's state as the user reads it, for example "Ringing", or empty without a call. */
const stateLabel = computed(() => {
  const state = props.call?.state;
  return state ? (STATE_LABELS[state] ?? state) : '';
});

/** Direction and the other party's number on one line, for example "inbound · +15555550199". */
const detail = computed(() =>
  [props.call?.direction, props.call?.externalNumber]
    .filter(Boolean)
    .join(' · '),
);
</script>

<template>
  <section aria-labelledby="call-heading" data-testid="call-card">
    <h2 id="call-heading" class="acme-heading">Call</h2>
    <p v-if="!call" class="acme-muted">No active call.</p>
    <div v-else>
      <div class="acme-call__state">{{ stateLabel }}</div>
      <div v-if="detail" class="acme-muted">{{ detail }}</div>
    </div>
  </section>
</template>

<style scoped>
.acme-call__state {
  font-weight: var(--dt-font-weight-bold);
}
</style>
