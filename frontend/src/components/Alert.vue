<template>
  <div class="alert" :class="`alert-${variant}`" role="status" aria-live="polite">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'info' },
});
</script>

<style scoped>
.alert {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  margin-top: 12px;
}
.alert-info { background: #eff6ff; color: #1e3a8a; border-color: #93c5fd; }
.alert-success { background: #f0fdf4; color: #166534; border-color: #86efac; }
.alert-warning { background: #fff7ed; color: #9a3412; border-color: #fdba74; }
.alert-error { background: #fef2f2; color: #991b1b; border-color: #fca5a5; }
</style>
