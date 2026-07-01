import { initRoteirosEditor } from './pages/roteiros/editor/index.js?v=20260701-destinos-autosave-fix';

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
