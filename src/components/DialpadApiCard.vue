<script setup lang="ts">
// "From Dialpad's API": a demo of what the backend can do with the idtoken's api key. While it
// rendered this page, the backend asked Dialpad's public API who the key belongs to (`users/me`)
// and passed a few fields on in the page data's `app` field. The call is unnecessary for the app
// and for demo purposes only; a real partner stores the api key and calls Dialpad when it needs to,
// not just when the panel loads. The key itself never reaches the page.
//
// `unavailable` means Dialpad's API refused, failed or was too slow, and the panel works anyway.
// `skipped` is local mode, whose mock idtoken has no real key. The card is hidden when the page
// data holds no result.
import { useRightbar } from '@dialpad/dialapp-external-sdk/vue';
import { computed } from 'vue';

import { readDialpadApi } from '../dialpadApi';

const { rightbar } = useRightbar();

/** The backend's demo result, read once: the page data's `app` never changes. */
const demo = computed(() => readDialpadApi(rightbar.app));
</script>

<template>
  <section
    v-if="demo"
    aria-labelledby="dialpad-api-heading"
    data-testid="dialpad-api-card"
  >
    <h2 id="dialpad-api-heading" class="acme-heading">From Dialpad's API</h2>
    <div v-if="demo.status === 'ok' && demo.user">
      <div class="acme-api__name">{{ demo.user.displayName ?? 'Unnamed' }}</div>
      <div v-if="demo.user.email" class="acme-muted">{{ demo.user.email }}</div>
      <div class="acme-muted">
        user {{ demo.user.id ?? '-' }} · {{ demo.user.state ?? 'unknown' }}
      </div>
      <p class="acme-muted">
        Fetched by the backend with the idtoken's api key (demo only).
      </p>
    </div>
    <p v-else-if="demo.status === 'skipped'" class="acme-muted">
      Skipped in local mode: the mock idtoken has no real api key.
    </p>
    <p v-else class="acme-muted">Dialpad API unavailable.</p>
  </section>
</template>

<style scoped>
.acme-api__name {
  font-weight: var(--dt-font-weight-bold);
}
</style>
