from django.test import TestCase

from documentos.services.adapters.docxtpl_render import render_docx_bytes
from documentos.services.resources_paths import resolve_resource_docx

from planos_trabalho.docxtpl_context import build_plano_docxtpl_context
from planos_trabalho.models import ProgramaSolicitante
from planos_trabalho.services import aplicar_textos_padrao
from planos_trabalho.services import atualizar_snapshot_diarias

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa
from .helpers import criar_servidor

PLACEHOLDERS_DO_MODELO = [
    "numero_plano_trabalho",
    "unidade",
    "contextualizacao",
    "metas",
    "atividades",
    "data_evento",
    "destinos",
    "horario_de_atendimento",
    "efetivos",
    "unidade_movel",
    "valor_do_plano",
    "recursos_necessarios",
    "coordenacao",
    "consideracao_final",
    "sede",
    "data_extenso",
    "nome_chefia",
    "cargo_chefia",
]


class DocxtplContextTests(TestCase):
    def setUp(self):
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa, efetivo=6)
        self.plano.programa = ProgramaSolicitante.objects.get(nome="PROGRAMA PARANÁ EM AÇÃO")
        self.plano.coordenador_adm = criar_servidor()
        aplicar_textos_padrao(self.plano)
        self.plano.save()
        atualizar_snapshot_diarias(self.plano)

    def test_contexto_cobre_todos_os_placeholders_do_modelo(self):
        contexto = build_plano_docxtpl_context(self.plano)
        for chave in PLACEHOLDERS_DO_MODELO:
            self.assertIn(chave, contexto, msg=chave)

    def test_valores_principais_iguais_ao_exemplo_maringa(self):
        contexto = build_plano_docxtpl_context(self.plano)
        self.assertEqual(contexto["numero_plano_trabalho"], "20/2026/ASCOM")
        self.assertEqual(contexto["destinos"], "Maringá/PR")
        self.assertEqual(contexto["data_evento"], "25 a 27 de junho de 2026")
        self.assertEqual(contexto["horario_de_atendimento"], "09:00 até 17:00")
        self.assertEqual(contexto["efetivos"], "6 Policiais Civis")
        self.assertIn("Valor total: R$7.234,68", contexto["valor_do_plano"])
        self.assertIn("4 x 100% + 1 x 15%", contexto["valor_do_plano"])
        self.assertIn("R$1.205,78", contexto["valor_do_plano"])
        self.assertIn("Papiloscopista Juliana Villela de Barros", contexto["coordenacao"])
        self.assertIn("município de Maringá/PR", contexto["contextualizacao"])
        self.assertEqual(contexto["sede"], "Curitiba/PR")
        self.assertEqual(contexto["nome_chefia"], "João Mário Nunes de Góes")
        self.assertEqual(contexto["cargo_chefia"], "Assessor de Comunicação Social")
        # Etapa 3 ainda não implementada: blocos saem vazios, não "None".
        self.assertEqual(contexto["metas"], "")
        self.assertEqual(contexto["atividades"], "")
        self.assertEqual(contexto["recursos_necessarios"], "")
        self.assertEqual(contexto["unidade_movel"], "")

    def test_render_docx_com_modelo_real(self):
        contexto = build_plano_docxtpl_context(self.plano)
        path = resolve_resource_docx("plano_trabalho.docx")
        conteudo = render_docx_bytes(template_path=path, context=contexto)
        self.assertGreater(len(conteudo), 1000)
        self.assertEqual(conteudo[:2], b"PK")
