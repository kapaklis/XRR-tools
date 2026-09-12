// Run: node tests/test_export_format.cjs (no browser or extra packages required).
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

// Minimal DOM for the real frontend event handlers and Python bridge boundary.
const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    value: selector === '#export-format' ? 'pdf' : '',
    listeners: {}, classList: {toggle() {}},
    addEventListener(event, callback) { this.listeners[event] = callback; },
  });
  return elements.get(selector);
}
const calls = [];
const context = vm.createContext({
  document: {querySelector: element, querySelectorAll: () => []},
  window: {addEventListener() {}},
  ResizeObserver: class { observe() {} },
  testAPI: {export: async (...args) => { calls.push(args); return {cancelled: true}; }},
});
vm.runInContext(readFileSync(join(__dirname, '../src/genx_figure_studio/ui/app.js'), 'utf8'), context);
vm.runInContext('api = testAPI; rows = [{visible: true}]; valid = true;', context);

(async () => {
  const selector = element('#export-format');
  for (const format of ['svg', 'png', 'pdf', 'png']) {
    selector.value = format;
    selector.listeners.change();
    for (const id of ['#export', '#export-top']) {
      assert.equal(element(id).textContent, `Export ${format.toUpperCase()} ↗`);
      await element(id).listeners.click();
      assert.equal(calls.at(-1)[2], format);
      assert.equal(selector.disabled, false);
    }
    assert.equal(element('#dpi-field').hidden, format !== 'png');
    assert.equal(element('#format-tag').textContent, format === 'png' ? 'RASTER' : 'VECTOR');
  }
  assert.equal(calls.length, 8);
  console.log('Export format regression passed: PDF/SVG/PNG, both buttons, cancellation and DPI visibility.');
})().catch(error => { console.error(error); process.exitCode = 1; });
