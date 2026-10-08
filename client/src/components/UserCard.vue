<script setup lang="ts">
// The Dialpad user, from the SDK's `state.user` (the host's `get/user`, asked once at start).
// The page data carries no user, so nothing from the idtoken reaches the page.
//
// `user` is null if Dialpad answered with none, which shows a short note instead. Status flags
// are as of the panel's start: Dialpad sends no event when they change.
import type { User } from '@dialpad/dialapp-external-sdk';
import { DtAvatar } from '@dialpad/dialtone/vue/lib/avatar';
import { computed } from 'vue';

const props = defineProps<{ user: User | null }>();

/** The boolean fields of `User` and their labels; only the ones that are true are shown. */
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

/** The user's full name, or an empty string when Dialpad sent none. */
const name = computed(() =>
  [props.user?.firstName, props.user?.lastName].filter(Boolean).join(' '),
);
/** Every email and phone number, joined for one line. */
const reach = computed(() =>
  [...(props.user?.emails ?? []), ...(props.user?.phoneNumbers ?? [])].join(
    ' · ',
  ),
);
/** The user, company and office ids, which is what a partner matches the Dialpad user by. */
const ids = computed(() =>
  props.user
    ? `user ${props.user.id ?? '-'} · company ${props.user.companyId ?? '-'} · office ${props.user.officeId ?? '-'}`
    : '',
);
/** The status flags that are on, for example "Available · On duty · Online". */
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
