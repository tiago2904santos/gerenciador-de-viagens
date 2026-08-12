import { initRoteirosEditor } from './roteiros/editor/index.js';

function bootRoteirosEditor() {
  const form = document.getElementById('roteiro-editor-form');
  if (!form) return;
  initRoteirosEditor();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootRoteirosEditor);
} else {
  bootRoteirosEditor();
}
