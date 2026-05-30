<template>
  <button class="btn" :class="`btn-${variant}`" :disabled="disabled">
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'primary' },
  disabled: { type: Boolean, default: false },
});
</script>

<style scoped>
.btn {
  min-height: 40px;
  border-radius: 10px;
  border: 1px solid transparent;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
.btn-secondary { background: #fff; color: var(--text); border-color: var(--border); }
.btn-danger { background: var(--danger); color: #fff; }
</style>
