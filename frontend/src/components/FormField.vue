<template>
  <label class="field">
    <span class="label">{{ label }}</span>
    <input
      class="input"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <small v-if="message" :class="`msg-${messageType}`">{{ message }}</small>
  </label>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  message: { type: String, default: '' },
  messageType: { type: String, default: 'info' },
});
defineEmits(['update:modelValue']);
</script>

<style scoped>
.field { display: grid; gap: 6px; }
.label { font-size: 13px; color: var(--muted); }
.input {
  min-height: 40px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  padding: 8px 10px;
}
.msg-info { color: var(--muted); }
.msg-error { color: #991b1b; }
.msg-success { color: #166534; }
</style>
