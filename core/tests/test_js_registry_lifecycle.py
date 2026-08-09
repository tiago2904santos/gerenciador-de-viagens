import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_REGISTRO = re.compile(
    r"registerEnhancer\(\s*(['\"])(?P<nome>[^'\"]+)\1\s*,(?P<resto>[^;]*?)\)\s*;",
    re.S,
)

# JS-02 — quem pode registrar enhancer SEM `destroy`, e por quê.
#
# O registry (`core/app.js`) chama `destroy(root)` quando um nó sai do DOM, mas
# `safelyDestroy` é no-op silencioso quando o componente não passou o terceiro
# argumento. Esta lista é a catraca: entrar nela exige uma razão escrita, e o
# padrão para componente novo é ter `destroy`.
#
# Duas razões legítimas — nenhuma delas é "não deu tempo":
#   a) o componente não registra nada em `document`/`window`: os listeners são
#      do próprio elemento e morrem com ele;
#   b) o listener global é delegação de página, registrado uma única vez no
#      escopo do módulo. Removê-lo ao tirar uma subárvore quebraria o resto.
SEM_DESTROY_JUSTIFICADO = {
    "components/card-toggle.js": "sem listener global; liga no elemento com guard data-*",
    "components/collection.js": "sem listener global; liga no container com data-collection-bound",
    "components/diaria-derivados.js": "sem listener global; `input` no próprio campo",
    "components/document-number-field.js": "sem listener global; guard documentNumberBound",
    "components/fields-init.js": "sem listener global; só orquestra outros componentes",
    "components/masks.js": "sem listener global; guard data-mask-bound por campo",
    "components/state-toggle.js": "sem listener global; guard data-cv-state-bound",
    "pages/eventos-detalhe.js": "sem listener global",
    "components/file-picker.js": "delegação de página: click/pagehide registrados uma vez no módulo",
    "core/app.js": "delegação de página: quickEdit tem guard de módulo, confirmSubmit roda uma vez",
    "cv-select.js": "delegação de página: click/keydown registrados uma vez no módulo",
}


class JavascriptRegistryLifecycleTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        cls.registry_source = (static_js / "core" / "app.js").read_text(encoding="utf-8")
        cls.collection_source = (
            static_js / "components" / "collection.js"
        ).read_text(encoding="utf-8")
        cls.overlay_source = (
            static_js / "components" / "overlay.js"
        ).read_text(encoding="utf-8")
        cls.autosave_source = (static_js / "autosave.js").read_text(
            encoding="utf-8"
        )

    def test_registry_has_a_single_name_without_a_dead_alias(self):
        """JS-12 — `CV.componentRegistry` era alias sem consumidor.

        O enunciado original dizia que `CV.registry` e `CV.componentRegistry`
        eram o mesmo objeto; a verificação refutou isso em runtime — eram dois
        literais distintos, `!==` entre si, com `registered` declarada duas
        vezes. O defeito real era mais simples: o segundo nome nunca teve um
        único consumidor em `static/js`, `templates/` ou Python.
        """
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        infratores = [
            path.relative_to(static_js).as_posix()
            for path in sorted(static_js.rglob("*.js"))
            if "componentRegistry" in path.read_text(encoding="utf-8-sig")
        ]
        self.assertEqual(infratores, [], f"alias morto de volta em: {infratores}")
        self.assertIn("window.CV.registry = {", self.registry_source)

    def test_registry_exposes_destroy_and_runs_cleanup_for_removed_nodes(self):
        self.assertIn("function destroy(root)", self.registry_source)
        self.assertIn("window.CV.registry = {", self.registry_source)
        self.assertIn("destroy: destroy", self.registry_source)
        self.assertIn(
            "Array.prototype.forEach.call(mutation.removedNodes, destroy)",
            self.registry_source,
        )

    def test_live_search_destroys_old_panel_before_replacing_it(self):
        destroy_call = "window.CV.registry.destroy(currentPanel)"
        replace_call = "currentPanel.replaceWith(nextPanel)"
        self.assertIn(destroy_call, self.collection_source)
        self.assertLess(
            self.collection_source.index(destroy_call),
            self.collection_source.index(replace_call),
        )

    def test_action_menu_registers_cleanup_that_restores_portaled_menu(self):
        self.assertIn("function restoreOwner(overlay)", self.overlay_source)
        self.assertIn("owner.parent.insertBefore(overlay", self.overlay_source)
        self.assertIn(
            'window.CV.registerEnhancer("overlay", init, destroy)',
            self.overlay_source,
        )

    def test_ajax_sensitive_components_register_as_enhancers(self):
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        contracts = {
            "autosave.js": "registerEnhancer('autosave'",
            "cv-select.js": "registerEnhancer('dropdowns'",
            "components/card-toggle.js": 'registerEnhancer("cardToggle"',
            "components/location-rows.js": 'registerEnhancer("locationRows"',
            "components/document-number-field.js": 'registerEnhancer("documentNumberField"',
            "components/fields-init.js": "registerEnhancer('fields'",
            "components/masks.js": "registerEnhancer('masks'",
            "components/state-toggle.js": "registerEnhancer('stateToggle'",
        }
        for relative_path, registration in contracts.items():
            with self.subTest(component=relative_path):
                source = (static_js / relative_path).read_text(encoding="utf-8")
                self.assertIn(registration, source)

    def test_inline_create_is_idempotent_enhancer(self):
        self.assertIn('window.CV.registerEnhancer("inlineCreate"', self.registry_source)
        self.assertIn('dataset.inlineCreateBound === "true"', self.registry_source)
        self.assertIn("if (quickEditBound) return", self.registry_source)

    def test_enhancers_without_destroy_are_only_the_justified_ones(self):
        """JS-02 — o ciclo de vida existe e 14 de 17 componentes não o implementavam.

        `core/app.js:126` aceita o terceiro argumento e o MutationObserver
        chama `destroy` em `removedNodes`; o que faltava era adoção. Sem ele,
        `picker.js` e `date-picker.js` deixavam um listener em `document`
        por instância — e `attach-signed-modal.js`, um por painel trazido via
        AJAX, porque o guard `BOUND` é por elemento e o listener é global.
        """
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        sem_destroy = {}
        for path in sorted(static_js.rglob("*.js")):
            if path.name.endswith(".bundle.js"):
                continue
            fonte = path.read_text(encoding="utf-8")
            for achado in _REGISTRO.finditer(fonte):
                argumentos = [a for a in achado.group("resto").split(",") if a.strip()]
                if len(argumentos) < 2:
                    sem_destroy[path.relative_to(static_js).as_posix()] = achado.group("nome")

        self.assertEqual(
            sorted(sem_destroy),
            sorted(SEM_DESTROY_JUSTIFICADO),
            "Enhancer sem `destroy` fora da lista justificada — ou implemente o "
            "`destroy`, ou acrescente o arquivo a SEM_DESTROY_JUSTIFICADO com a razão.",
        )

    def test_components_with_destroy_undo_every_global_listener_they_add(self):
        """JS-02 — `destroy` que não desfaz nada é pior que a ausência dele: passa no gate."""
        static_js = Path(settings.BASE_DIR) / "static" / "js"
        for relativo in (
            "components/picker.js",
            "components/date-picker.js",
            "components/attach-signed-modal.js",
            "components/location-rows.js",
        ):
            with self.subTest(componente=relativo):
                fonte = (static_js / relativo).read_text(encoding="utf-8")
                globais = len(
                    re.findall(r"(?:document|window)\.addEventListener", fonte)
                ) - len(re.findall(r"addEventListener\(\s*['\"]DOMContentLoaded", fonte))
                remocoes = len(
                    re.findall(r"(?:document|window)\.removeEventListener", fonte)
                )
                self.assertEqual(
                    remocoes,
                    globais,
                    f"{relativo}: {globais} listener(es) global(is) e {remocoes} remoção(ões)",
                )
                self.assertIn("instancias.push(", fonte)
                self.assertIn("function destroy(scope)", fonte)

    def test_registry_loads_before_autosave(self):
        # NOVO-12: ordem de carga do shell está no bundle JS.
        bundle = (
            Path(settings.BASE_DIR) / "static" / "js" / "shell.bundle.js"
        ).read_text(encoding="utf-8")
        self.assertLess(
            bundle.index(">>> js/core/app.js >>>"),
            bundle.index(">>> js/autosave.js >>>"),
        )

    def test_autosave_unregisters_global_and_form_listeners_on_destroy(self):
        self.assertIn(
            "registerEnhancer('autosave', window.CV.autosave.init, destroy)",
            self.autosave_source,
        )
        for contract in (
            "form.removeEventListener('input', onInput, true)",
            "form.removeEventListener('change', onChange, true)",
            "form.removeEventListener('blur', onBlur, true)",
            "form.removeEventListener('submit', onSubmit, true)",
            "activeInstances.delete(instance)",
            "forms.delete(form)",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.autosave_source)

        self.assertEqual(
            self.autosave_source.count("document.addEventListener('click'"),
            1,
        )
        self.assertEqual(
            self.autosave_source.count("window.addEventListener('beforeunload'"),
            1,
        )
