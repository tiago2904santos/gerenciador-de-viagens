"""`NOVO-20260824-173723-37e9862b4c2a` — pedido de KM no aviso e envio de RT/DB.

Duas pontas da mesma conversa de WhatsApp:

1. O aviso de liberação do MOTORISTA leva junto o pedido dos KM de cada trecho,
   porque é ele quem lê o odômetro e é esse dado que falta para fechar o diário.
2. Quando RT e diário estão preenchidos, o mesmo menu passa a oferecer o envio
   dos PDFs.

O que se mede aqui é o CONTRATO com o front: o presenter entrega as rotas em
JSON e o gate de pendências, e o fragmento de menu renderiza o gancho que o
`prestacoes-docs-wa.js` escuta. A montagem da mensagem e a folha de
compartilhamento são do JS e ficam fora — não há Node local (ver
`vitest-sem-node-local`).
"""

from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse

from prestacoes_contas.models import DiarioBordo
from prestacoes_contas.models import DiarioBordoTrecho
from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.presenters import apresentar_prestacao_servidor_card
from prestacoes_contas.services import pendencias_envio_rt_db
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin


class EnvioDocumentosWhatsAppTests(PrestacaoFixturesMixin, TestCase):
    def setUp(self):
        self.setUpPrestacaoFixtures()
        self.motorista = self.criar_servidor("Motorista Um")
        self.carona = self.criar_servidor("Servidor Dois")
        self.fixture = self.criar_prestacao(
            numero=1,
            servidores=[self.motorista, self.carona],
            trechos_roteiro=2,
        )
        self.fixture.oficio.motorista = self.motorista
        self.fixture.oficio.save(update_fields=["motorista"])
        # Releitura obrigatória: `is_motorista` compara com
        # `self.prestacao.oficio.motorista_id`, e as instâncias que a fixture
        # devolveu carregam o ofício em cache de ANTES de haver motorista.
        self.ps_motorista = PrestacaoServidor.objects.get(
            prestacao=self.fixture.prestacao, servidor=self.motorista
        )
        self.ps_carona = PrestacaoServidor.objects.get(
            prestacao=self.fixture.prestacao, servidor=self.carona
        )

    # ── auxiliares ──

    def _preencher_rt(self):
        RelatorioTecnico.objects.update_or_create(
            prestacao=self.fixture.prestacao,
            defaults={
                "motivo": "Operação conjunta",
                "atividade": "Apoio às equipes de campo",
                "conclusao": "Objetivo alcançado",
            },
        )

    def _preencher_diario(self, *, km=True, abastecimento=True):
        diario, _ = DiarioBordo.objects.get_or_create(prestacao=self.fixture.prestacao)
        for ordem in range(2):
            DiarioBordoTrecho.objects.update_or_create(
                diario=diario,
                ordem=ordem,
                defaults={
                    "km_inicial": 1000 + ordem * 100 if km else None,
                    "km_final": 1050 + ordem * 100 if km else None,
                    "abastecimento": False if abastecimento else None,
                },
            )
        return diario

    def _card(self, ps):
        return apresentar_prestacao_servidor_card(ps, menus_sob_demanda=False)

    def _fragmento_menu(self, ps):
        return self.client.get(reverse("prestacoes_contas:card_menus", args=[ps.pk]))

    # ── pendências ──

    def test_rt_em_branco_e_pendencia_para_qualquer_servidor(self):
        """RT é `blank=True` no banco inteiro: sem este gate, o PDF sai vazio.

        É a razão de o serviço existir — nada no modelo impede gerar e mandar um
        relatório com os três blocos de texto em branco.
        """
        for ps in (self.ps_motorista, self.ps_carona):
            with self.subTest(servidor=ps.servidor.nome):
                pendencias = pendencias_envio_rt_db(ps)
                self.assertTrue(pendencias)
                self.assertIn("descrição do evento", pendencias[0])
                self.assertIn("objetivo da participação", pendencias[0])
                self.assertIn("conclusão", pendencias[0])

    def test_com_rt_preenchido_quem_nao_dirige_ja_pode_receber(self):
        """O diário não entra na conta de quem não o assina."""
        self._preencher_rt()

        self.assertEqual(pendencias_envio_rt_db(self.ps_carona), [])

    def test_motorista_sem_km_no_diario_continua_pendente(self):
        self._preencher_rt()
        self._preencher_diario(km=False, abastecimento=False)

        pendencias = pendencias_envio_rt_db(self.ps_motorista)

        self.assertEqual(len(pendencias), 2)
        self.assertIn("KM inicial e final de 2 trecho(s)", pendencias[0])
        self.assertIn("abastecimento em 2 trecho(s)", pendencias[1])

    def test_abastecimento_nulo_conta_como_nao_respondido(self):
        """`null` é "ninguém respondeu", não "não abasteceu".

        O campo é `BooleanField(null=True)`; tratar nulo como `False` mandaria
        para o diário assinado uma resposta que ninguém deu.
        """
        self._preencher_rt()
        self._preencher_diario(km=True, abastecimento=False)

        pendencias = pendencias_envio_rt_db(self.ps_motorista)

        self.assertEqual(len(pendencias), 1)
        self.assertIn("abastecimento", pendencias[0])

    def test_tudo_preenchido_libera_o_motorista(self):
        self._preencher_rt()
        self._preencher_diario()

        self.assertEqual(pendencias_envio_rt_db(self.ps_motorista), [])

    def test_motorista_sem_diario_pede_para_abrir_a_tela(self):
        self._preencher_rt()

        pendencias = pendencias_envio_rt_db(self.ps_motorista)

        self.assertEqual(len(pendencias), 1)
        self.assertIn("Diário de Bordo", pendencias[0])

    # ── presenter ──

    def test_so_o_motorista_recebe_o_pedido_de_km(self):
        card_motorista = self._card(self.ps_motorista)
        card_carona = self._card(self.ps_carona)

        rotas = json.loads(card_motorista["servidores"][0]["whatsapp_trechos"])
        self.assertEqual(len(rotas), 2)
        self.assertEqual(card_carona["servidores"][0]["whatsapp_trechos"], "")

    def test_rotas_saem_em_json_valido_com_a_seta_legivel(self):
        """`ensure_ascii=False`: a rota atravessa o atributo e o `dataset` inteira.

        A seta é o separador que o operador lê na conversa; escapada (`\\u2192`)
        ela chegaria assim ao WhatsApp.
        """
        card = self._card(self.ps_motorista)

        bruto = card["servidores"][0]["whatsapp_trechos"]
        self.assertIn("→", bruto)
        self.assertIsInstance(json.loads(bruto), list)

    def test_gate_de_envio_acompanha_as_pendencias(self):
        card = self._card(self.ps_carona)
        self.assertFalse(card["servidores"][0]["envio_docs_ok"])
        self.assertTrue(card["servidores"][0]["envio_docs_motivo"])

        self._preencher_rt()

        # Instância nova, como faz a requisição seguinte: o RT é OneToOne reverso
        # e o Django guarda no objeto a ausência já consultada — reaproveitar o
        # `ps` mediria o cache, não o gate.
        card = self._card(
            PrestacaoServidor.objects.get(pk=self.ps_carona.pk)
        )
        self.assertTrue(card["servidores"][0]["envio_docs_ok"])
        self.assertEqual(card["servidores"][0]["envio_docs_motivo"], "")

    # ── fragmento de menu ──

    def test_menu_oferece_o_envio_quando_esta_pronto(self):
        self._preencher_rt()
        self._preencher_diario()

        fragmento = self._fragmento_menu(self.ps_motorista)

        self.assertContains(fragmento, "data-docs-wa-send")
        self.assertContains(fragmento, "Enviar RT e Diário de Bordo")

    def test_menu_desabilitado_diz_o_que_falta_em_vez_de_sumir(self):
        """Item que some é item que o operador procura sem achar."""
        fragmento = self._fragmento_menu(self.ps_carona)

        self.assertNotContains(fragmento, "data-docs-wa-send")
        self.assertContains(fragmento, 'aria-disabled="true"')
        self.assertContains(fragmento, "Enviar Relatório Técnico")
        self.assertContains(fragmento, "Preencha no Relatório Técnico")

    def test_gatilho_do_card_leva_as_urls_dos_pdfs(self):
        """O menu aberto é transplantado para o `<body>` e perde os ancestrais.

        Por isso as URLs moram no GATILHO, não no item — é lá que
        `prestacoes-docs-wa.js` volta para achar o contexto do servidor.
        """
        self._preencher_rt()
        self._preencher_diario()
        resposta = self.client.get(reverse("prestacoes_contas:index"))

        self.assertContains(resposta, "data-docs-rt-url")
        self.assertContains(resposta, "data-wa-trechos")

    def test_quem_nao_dirige_nao_leva_url_de_diario(self):
        """Só o motorista assina o diário; anexá-lo aos demais seria vazamento."""
        card = self._card(self.ps_carona)

        self.assertFalse(card["servidores"][0]["is_motorista"])


class EnvioDocumentosSemViaturaTests(PrestacaoFixturesMixin, TestCase):
    """Ofício sem roteiro: o pedido de KM não tem o que listar e não sai."""

    def setUp(self):
        self.setUpPrestacaoFixtures()
        self.servidor = self.criar_servidor("Servidor Sozinho")
        self.fixture = self.criar_prestacao(
            numero=7, servidores=[self.servidor], com_roteiro=False
        )
        self.ps = self.fixture.prestacoes_servidor[0]

    def test_sem_roteiro_nao_ha_pedido_de_km(self):
        card = apresentar_prestacao_servidor_card(self.ps, menus_sob_demanda=False)

        self.assertEqual(card["servidores"][0]["whatsapp_trechos"], "")
