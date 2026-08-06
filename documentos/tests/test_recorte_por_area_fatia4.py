"""BE-09, fatia 4 — `prestacoes_contas` e `documentos`.

Esta é a fatia onde o desenho do `BE-09` encosta no caminho **assíncrono**, e por
isso ela tem uma classe que as anteriores não tinham.

`GeracaoAssincronaTests` cobre `_objeto_do_job`, que é o único ponto do sistema
onde uma função genérica lê por `pk` modelos de **cinco apps diferentes** —
`Oficio`, `PlanoTrabalho`, `OrdemServico`, `TermoAutorizacao` e `Servidor` — que
o `BE-09` migra em fatias diferentes. Escrevê-la com `all_objects` quebrou quatro
testes de imediato: `Servidor` só ganha esse manager na fatia 5. A forma certa
ali é `_base_manager`, que existe em todo modelo e nunca recorta.

O contrato do `DB-04` também aparece aqui: quem separa as áreas no cache
documental é a **referência** (`oficio_id`, `evento_id`, `termo_id`,
`servidor_id`), obrigatória desde aquele ID — não a área ambiente. Por isso a
consulta do cache usa `all_objects`: ela precisa dar o mesmo resultado no request
e na worker, e o comentário que já estava lá dizia exatamente isso.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.test import TestCase

from core.tests.test_area_scoped_manager import com_request
from core.tests.test_area_scoped_manager import sem_request
from documentos.models import DocumentoArtefato
from documentos.models import DocumentoGeracao
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from oficios.models import Oficio
from prestacoes_contas.models import ModeloTextoRelatorioTecnico
from prestacoes_contas.models import PrestacaoContas
from usuarios.models import AreaTrabalho


class RecorteChegaNosQuatroModelosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="F4-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="F4-B")

    def _visiveis(self, modelo):
        with com_request(self.area):
            return set(modelo.objects.values_list("pk", flat=True))

    def test_prestacao_contas(self):
        with sem_request():
            contador = iter(range(100))

            def prestacao(area):
                # `prestacoes_contas/signals.py` cria a prestação no `post_save`
                # do ofício; criar outra aqui estoura o `unique` de `oficio_id`.
                oficio = Oficio.objects.create(
                    area=area, numero=next(contador) + 1, ano=2026, assunto="X",
                )
                return PrestacaoContas.all_objects.get(oficio=oficio)

            meu, alheio = prestacao(self.area), prestacao(self.outra)

        visiveis = self._visiveis(PrestacaoContas)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_modelo_texto_relatorio_tecnico(self):
        with sem_request():
            contador = iter(range(100))
            meu, alheio = [
                ModeloTextoRelatorioTecnico.objects.create(
                    area=area, campo="atividades", nome=f"Modelo {next(contador)}", texto="…",
                )
                for area in (self.area, self.outra)
            ]

        visiveis = self._visiveis(ModeloTextoRelatorioTecnico)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_documento_artefato(self):
        with sem_request():
            contador = iter(range(100))

            def artefato(area):
                oficio = Oficio.objects.create(
                    area=area, numero=next(contador) + 50, ano=2026, assunto="X",
                )
                return DocumentoArtefato.objects.create(
                    tipo=DocumentoTipo.OFICIO.value,
                    formato=DocumentoFormato.PDF.value,
                    oficio=oficio,
                    cache_key="k" * 64,
                    hash_sha256="h" * 64,
                )

            meu, alheio = artefato(self.area), artefato(self.outra)

        visiveis = self._visiveis(DocumentoArtefato)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_documento_geracao(self):
        with sem_request():
            meu, alheio = [
                DocumentoGeracao.objects.create(area=area, parametros={})
                for area in (self.area, self.outra)
            ]

        visiveis = self._visiveis(DocumentoGeracao)

        self.assertIn(meu.pk, visiveis)
        self.assertNotIn(alheio.pk, visiveis)

    def test_os_quatro_declaram_o_par_de_managers(self):
        modelos = (PrestacaoContas, ModeloTextoRelatorioTecnico, DocumentoArtefato, DocumentoGeracao)
        for modelo in modelos:
            with self.subTest(modelo=modelo.__name__):
                self.assertIs(modelo._default_manager, modelo.all_objects)
                self.assertEqual(modelo._meta.default_manager_name, "all_objects")


class GeracaoAssincronaTests(TestCase):
    """`_objeto_do_job` lê por pk modelos que o `BE-09` migra em fatias diferentes."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="ASY-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="ASY-B")

    def test_le_modelo_ja_recortado_com_a_area_do_job(self):
        """`Oficio` já tem o manager (fatia 2). A área do job é a que manda."""
        from documentos.services.async_generation import _objeto_do_job

        with sem_request():
            oficio = Oficio.objects.create(area=self.outra, numero=1, ano=2026, assunto="X")

        with com_request(self.area):
            achado = _objeto_do_job(Oficio, pk=oficio.pk, area_id=self.outra.pk)

        self.assertEqual(achado, oficio)

    def test_le_modelo_ainda_nao_recortado(self):
        """`Servidor` só é migrado na fatia 5, e não tem `all_objects`.

        Este é o teste que reprovou a primeira versão desta fatia — escrita com
        `all_objects`, ela dava `AttributeError` em quatro testes de geração de
        documento. `_base_manager` existe em todo modelo, migrado ou não.
        """
        from cadastros.models import Servidor
        from documentos.services.async_generation import _objeto_do_job

        with sem_request():
            servidor = Servidor.objects.create(nome="Fulano", area=self.outra)

        with com_request(self.area):
            achado = _objeto_do_job(Servidor, pk=servidor.pk, area_id=self.outra.pk)

        self.assertEqual(achado, servidor)

    def test_recusa_quando_a_area_do_job_nao_bate(self):
        """A conferência à mão continua sendo o portão — não o manager."""
        from documentos.services.async_generation import _objeto_do_job

        with sem_request():
            oficio = Oficio.objects.create(area=self.outra, numero=2, ano=2026, assunto="X")

        with com_request(self.outra), self.assertRaises(Oficio.DoesNotExist):
            _objeto_do_job(Oficio, pk=oficio.pk, area_id=self.area.pk)


class CacheDocumentalIndependeDaAreaAmbienteTests(TestCase):
    """`DB-04` + `BE-09`: quem separa as áreas é a referência, não o ambiente."""

    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="CAC-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="CAC-B")
        self.chave = "c" * 64

    def _artefato(self, oficio):
        artefato = DocumentoArtefato.all_objects.create(
            tipo=DocumentoTipo.OFICIO.value,
            formato=DocumentoFormato.PDF.value,
            oficio=oficio,
            cache_key=self.chave,
            hash_sha256="h" * 64,
        )
        artefato.arquivo.save(f"c-{oficio.pk}.pdf", ContentFile(b"%PDF-1.4"), save=True)
        return artefato

    def test_o_cache_acha_o_artefato_com_e_sem_request(self):
        """O mesmo resultado nos dois contextos é o ponto: a geração roda na
        worker, e um cache que dependesse da área ativa viraria nada lá."""
        from documentos.services.document_cache import get_cached_document_artifact

        with sem_request():
            oficio = Oficio.objects.create(area=self.outra, numero=3, ano=2026, assunto="X")
            artefato = self._artefato(oficio)

        def buscar():
            return get_cached_document_artifact(
                tipo=DocumentoTipo.OFICIO,
                formato=DocumentoFormato.PDF,
                cache_key=self.chave,
                oficio_id=oficio.pk,
            )

        with sem_request():
            self.assertEqual(buscar(), artefato)
        with com_request(self.area):
            self.assertEqual(buscar(), artefato, msg="o cache virou nada por causa da área ativa")

    def test_a_referencia_continua_separando_as_areas(self):
        """O `DB-04` não pode ter sido afrouxado: mesma chave, outro ofício."""
        from documentos.services.document_cache import get_cached_document_artifact

        with sem_request():
            alheio = Oficio.objects.create(area=self.outra, numero=4, ano=2026, assunto="X")
            meu = Oficio.objects.create(area=self.area, numero=5, ano=2026, assunto="X")
            self._artefato(alheio)

        with com_request(self.area):
            achado = get_cached_document_artifact(
                tipo=DocumentoTipo.OFICIO,
                formato=DocumentoFormato.PDF,
                cache_key=self.chave,
                oficio_id=meu.pk,
            )

        self.assertIsNone(achado)


class PrestacaoNasceNaAreaDoOficioTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="SIG-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="SIG-B")

    def test_o_signal_nao_duplica_a_prestacao_do_oficio_de_outra_area(self):
        """`prestacoes_contas/signals.py` faz `get_or_create(oficio=...)`. Com
        `objects` e área do ofício diferente da ativa, o `get` não acharia a
        prestação já existente e o `create` duplicaria — o signal roda a cada
        mudança de equipe do ofício."""
        from prestacoes_contas.signals import _sincronizar_prestacao_servidores

        with sem_request():
            # O `post_save` do ofício já cria a prestação; é justamente ela que o
            # `get_or_create` da segunda chamada precisa encontrar.
            oficio = Oficio.objects.create(area=self.outra, numero=6, ano=2026, assunto="X")

        with com_request(self.area):
            _sincronizar_prestacao_servidores(oficio)

        self.assertEqual(
            PrestacaoContas.all_objects.filter(oficio=oficio).count(),
            1,
            msg="o signal criou uma segunda prestação para o mesmo ofício",
        )
