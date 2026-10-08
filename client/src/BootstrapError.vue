<script setup lang="ts">
// Shown instead of the panel when the SDK can't start: the page isn't framed by Dialpad (for
// example it was opened directly in a tab), the page data is invalid, or Dialpad never answered.
// Nothing else is rendered, because there is no working host to talk to.
</script>

<template>
  <p role="alert" data-testid="bootstrap-error">
    Open this panel from Dialpad.
  </p>
</template>
