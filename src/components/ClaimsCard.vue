<script setup lang="ts">
// The signed-in Dialpad user: every non-sensitive idtoken claim, from the page data.
// Never `api_key` (the library keeps it server-side) and nothing from `csr`.
import { DtAvatar } from '@dialpad/dialtone/vue/lib/avatar';
import { computed } from 'vue';

export interface Claims {
  userId: number;
  companyId: number;
  officeId: number;
  name: string | null;
  email: string | null;
  phoneNumber: string | null;
  imageUrl: string | null;
}

const props = defineProps<{ user: Claims }>();

const contactLine = computed(() =>
  [props.user.email, props.user.phoneNumber].filter(Boolean).join(' · '),
);
</script>

<template>
  <section aria-labelledby="claims-heading" data-testid="claims-card">
    <h2 id="claims-heading" class="acme-heading">You</h2>
    <div class="acme-claims">
      <DtAvatar
        :full-name="user.name ?? ''"
        :image-src="user.imageUrl ?? ''"
        :image-alt="user.name ?? 'Your avatar'"
        :size="400"
      />
      <div>
        <div class="acme-claims__name">{{ user.name }}</div>
        <div class="acme-muted">{{ contactLine }}</div>
        <div class="acme-muted">
          user {{ user.userId }} · company {{ user.companyId }} · office
          {{ user.officeId }}
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.acme-claims {
  display: flex;
  gap: var(--dt-space-400);
  align-items: center;
}
.acme-claims__name {
  font-weight: var(--dt-font-weight-bold);
}
</style>
