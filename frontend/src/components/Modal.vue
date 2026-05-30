<template>
  <div v-if="open" class="overlay" role="dialog" aria-modal="true">
    <div class="panel">
      <div class="head">
        <h3>{{ title }}</h3>
        <button class="close" @click="$emit('close')" aria-label="Close">×</button>
      </div>
      <div class="body">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Modal' },
});
defineEmits(['close']);
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: grid;
  place-items: center;
  padding: 16px;
}
.panel {
  width: min(560px, 100%);
  background: #fff;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.body { padding: 14px; }
.close {
  border: 1px solid var(--border);
  border-radius: 8px;
  min-height: 32px;
  min-width: 32px;
  background: #fff;
}
h3 { margin: 0; }
</style>
