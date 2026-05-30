<template>
  <div class="table-wrap">
    <table class="table" v-if="rows.length">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key">{{ col.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in rows" :key="idx">
          <td v-for="col in columns" :key="col.key">{{ row[col.key] }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">{{ emptyText }}</div>
  </div>
</template>

<script setup>
defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  emptyText: { type: String, default: 'No data available' },
});
</script>

<style scoped>
.table-wrap {
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
th, td {
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid #e7eef7;
  font-size: 13px;
}
th { background: #f1f5f9; }
.empty {
  padding: 14px;
  color: var(--muted);
}
</style>
