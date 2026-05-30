import { createApp } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js';

const sampleRows = [
  { name: 'Alex Rivera', role: 'Student', hours: 16 },
  { name: 'Jordan Lee', role: 'Supervisor', hours: 22 },
];

const style = document.createElement('link');
style.rel = 'stylesheet';
style.href = '/frontend/src/styles/main.css';
document.head.appendChild(style);

const Navbar = {
  props: ['title', 'subtitle'],
  template: `
    <header class="card" style="margin-top:0;">
      <h1 style="margin:0; font-size:22px;">{{ title }}</h1>
      <p style="margin:4px 0 0 0; color:var(--muted);">{{ subtitle }}</p>
    </header>
  `,
};

const Alert = {
  props: { variant: { type: String, default: 'info' } },
  template: `<div class="card" :style="variantStyle"><slot /></div>`,
  computed: {
    variantStyle() {
      const map = {
        info: 'background:#eff6ff;color:#1e3a8a;border-color:#93c5fd;',
        success: 'background:#f0fdf4;color:#166534;border-color:#86efac;',
        warning: 'background:#fff7ed;color:#9a3412;border-color:#fdba74;',
        error: 'background:#fef2f2;color:#991b1b;border-color:#fca5a5;',
      };
      return map[this.variant] || map.info;
    },
  },
};

const Button = {
  props: {
    variant: { type: String, default: 'primary' },
    disabled: { type: Boolean, default: false },
  },
  template: `<button :disabled="disabled" :style="buttonStyle"><slot /></button>`,
  computed: {
    buttonStyle() {
      const base = 'min-height:40px;border-radius:10px;padding:8px 12px;font-weight:600;cursor:pointer;';
      const map = {
        primary: 'background:#1d4ed8;color:#fff;border:1px solid #1d4ed8;',
        secondary: 'background:#fff;color:#0f172a;border:1px solid #dbe2ea;',
        danger: 'background:#dc2626;color:#fff;border:1px solid #dc2626;',
      };
      const disabled = this.disabled ? 'opacity:.6;cursor:not-allowed;' : '';
      return `${base}${map[this.variant] || map.primary}${disabled}`;
    },
  },
};

const DataTable = {
  props: ['columns', 'rows', 'emptyText'],
  template: `
    <div class="card" style="padding:0; overflow:auto;">
      <table v-if="rows.length" style="width:100%; border-collapse:collapse;">
        <thead>
          <tr>
            <th v-for="col in columns" :key="col.key" style="text-align:left;padding:10px;border-bottom:1px solid #e7eef7;background:#f1f5f9;">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx">
            <td v-for="col in columns" :key="col.key" style="padding:10px;border-bottom:1px solid #e7eef7;">{{ row[col.key] }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else style="padding:14px;color:var(--muted);">{{ emptyText }}</div>
    </div>
  `,
};

createApp({
  components: { Navbar, Alert, Button, DataTable },
  data() {
    return {
      rows: sampleRows,
      columns: [
        { key: 'name', label: 'Name' },
        { key: 'role', label: 'Role' },
        { key: 'hours', label: 'Hours' },
      ],
    };
  },
  template: `
    <main class="container">
      <Navbar title="CSUF Scheduler" subtitle="Component Library Preview" />
      <Alert variant="info">Reusable components scaffolded for Phase 2.</Alert>
      <section class="card">
        <h2>Navigation</h2>
        <p style="color:var(--muted); margin-top:0;">Legacy template app is still available while migration continues.</p>
        <div class="row">
          <a href="/" style="text-decoration:none;"><Button variant="secondary">Open Main Scheduler UI</Button></a>
        </div>
      </section>
      <section class="card">
        <h2>Buttons</h2>
        <div class="row">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="danger">Danger</Button>
          <Button :disabled="true">Disabled</Button>
        </div>
      </section>
      <section class="card">
        <h2>Data Table</h2>
        <DataTable :columns="columns" :rows="rows" empty-text="No records found" />
      </section>
    </main>
  `,
}).mount('#app');
