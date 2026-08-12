/**
 * Ponte do editor modular com o script legado do mapa (roteiros-map.js).
 */
export function createMapaModule() {
  function boot() {
    if (window.CV.roteiros.map && typeof window.CV.roteiros.map.boot === 'function') {
      window.CV.roteiros.map.boot();
    }
  }

  if (window.CV.roteiros.editor) {
    boot();
  } else {
    window.addEventListener('roteiros:editor-ready', boot, { once: true });
  }

  return {
    name: 'mapa',
    refresh: function () {
      if (window.CV.roteiros.map && typeof window.CV.roteiros.map.boot === 'function') {
        window.CV.roteiros.map.boot();
      }
    },
  };
}
