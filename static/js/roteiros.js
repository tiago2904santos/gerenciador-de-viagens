import { initRoteirosEditor } from './pages/roteiros/editor/index.js?v=20260602';

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
