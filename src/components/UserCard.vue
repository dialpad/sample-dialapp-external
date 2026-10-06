<script setup lang="ts">
// The Dialpad user, from the SDK's `state.user` (the host's `get/user`, asked once at start).
// The page data carries no user, so nothing from the idtoken reaches the page.
import type { User } from '@dialpad/dialapp-external-sdk';
import { DtAvatar } from '@dialpad/dialtone/vue/lib/avatar';
import { computed } from 'vue';

const props = defineProps<{ user: User | null }>();

const FLAGS: [keyof User, string][] = [
  ['isAdmin', 'Admin'],
  ['isSuperAdmin', 'Super admin'],
  ['isAvailable', 'Available'],
  ['isOnDuty', 'On duty'],
  ['isOnline', 'Online'],
  ['doNotDisturb', 'Do not disturb'],
  ['muted', 'Muted'],
  ['isOnUberconference', 'On Uberconference'],
];

const name = computed(() =>
  [props.user?.firstName, props.user?.lastName].filter(Boolean).join(' '),
);
const reach = computed(() =>
  [...(props.user?.emails ?? []), ...(props.user?.phoneNumbers ?? [])].join(
    ' · ',
  ),
);
const ids = computed(() =>
  props.user
    ? `user ${props.user.id ?? '-'} · company ${props.user.companyId ?? '-'} · office ${props.user.officeId ?? '-'}`
    : '',
);
const status = computed(() =>
  FLAGS.filter(([flag]) => props.user?.[flag] === true)
    .map(([, label]) => label)
    .join(' · '),
);
</script>

<template>
  <section aria-labelledby="user-heading" data-testid="user-card">
    <h2 id="user-heading" class="acme-heading">You</h2>
    <p v-if="!user" class="acme-muted">
      Dialpad didn't send your user details.
    </p>
    <div v-else class="acme-user">
      <DtAvatar
        :full-name="name"
        :image-src="user.imageUrl ?? ''"
        :image-alt="name || 'Your avatar'"
        :size="400"
      />
      <div>
        <div class="acme-user__name">{{ name }}</div>
        <div v-if="user.jobTitle" class="acme-muted">{{ user.jobTitle }}</div>
        <div v-if="reach" class="acme-muted">{{ reach }}</div>
        <div class="acme-muted">{{ ids }}</div>
        <div v-if="user.licenses.length > 0" class="acme-muted">
          Licenses: {{ user.licenses.join(', ') }}
        </div>
        <div v-if="status" class="acme-muted">{{ status }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.acme-user {
  display: flex;
  gap: var(--dt-space-400);
  align-items: center;
}
.acme-user__name {
  font-weight: var(--dt-font-weight-bold);
}
</style>
