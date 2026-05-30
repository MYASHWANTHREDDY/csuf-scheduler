<template>
  <header class="navbar">
    <div>
      <h1>{{ title }}</h1>
      <p>{{ subtitle }}</p>
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, default: 'CSUF Scheduler' },
  subtitle: { type: String, default: '' },
});
</script>

<style scoped>
.navbar {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
}
h1 { margin: 0; font-size: 22px; }
p { margin: 4px 0 0 0; color: var(--muted); }
</style>
