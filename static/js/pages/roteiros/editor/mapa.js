/**
 * Ponte do editor modular com o script legado do mapa (roteiros-map.js).
 */
export function createMapaModule() {
  function boot() {
    if (typeof window.RoteirosMapBoot === 'function') {
      window.RoteirosMapBoot();
    }
  }

  if (window.RoteirosEditor) {
    boot();
  } else {
    window.addEventListener('roteiros:editor-ready', boot, { once: true });
  }

  return {
    name: 'mapa',
    refresh: function () {
      if (typeof window.RoteirosMapBoot === 'function') {
        window.RoteirosMapBoot();
      }
    },
  };
}
