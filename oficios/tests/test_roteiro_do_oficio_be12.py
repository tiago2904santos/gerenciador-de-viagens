"""`BE-12` — caracterização da regra de vínculo/cópia de roteiro do ofício.

`oficios/route_views.py::wizard_roteiro` tem 165 linhas úteis e 33 ramos, e dentro dela
mora a regra que o catálogo chama de "a que mais gera bug de dados neste sistema":
**roteiro é compartilhado entre ofícios**, e é esta view que decide se o ofício reaproveita
um roteiro existente ou grava uma cópia própria.

Medido com `coverage` antes de escrever isto: o bloco inteiro de
`if form.is_valid() and validated["ok"]` (`route_views.py:125-160`) tinha **cobertura zero**.
Nenhum teste do repositório exercitava o reuso-sem-cópia, a materialização de rascunho novo,
nem qualquer das quatro saídas de navegação do caminho válido.

Estes testes descrevem o comportamento de hoje e foram provados verdes **antes** da extração
para service. O que travam:

- reaproveitar não pode virar cópia, e copiar não pode virar alteração do roteiro alheio;
- um roteiro não-rascunho, que pertence a outros ofícios, nunca é modificado;
- cada ação do rodapé leva ao seu destino, com a sua mensagem.

As datas são relativas a hoje de propósito: a escolha entre `wizard_documentos` e
`wizard_justificativa` depende da antecedência da saída contra o prazo configurado, e data
fixa faria o teste mudar de significado com o tempo.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.testing import area_de_teste
from core.testing import vincular_area
from oficios.models import Oficio
from roteiros.services import editor_state_builder
from roteiros.models import Roteiro


def _mensagens(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class RoteiroDoOficioCaracterizacaoTests(TestCase):
    """O que a Etapa 2 do ofício faz hoje ao salvar, congelado."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="be12_tester", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        area = area_de_teste()

        self.cargo = Cargo.objects.create(area=area, nome="Cargo BE12")
        self.combustivel = Combustivel.objects.create(area=area, nome="Flex BE12")
        self.unidade = Unidade.objects.create(area=area, nome="Unidade BE12", sigla="UB12")
        self.servidor = Servidor.objects.create(
            area=area, nome="Viajante BE12", cargo=self.cargo, cpf="11122233344"
        )
        self.motorista = Servidor.objects.create(
            area=area, nome="Motorista BE12", cargo=self.cargo, cpf="99988877766", unidade=self.unidade
        )
        self.viatura = Viatura.objects.create(
            area=area,
            placa="BEZ1212",
            modelo="Modelo BE12",
            combustivel=self.combustivel,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
        )
        self.viatura.motoristas.add(self.motorista)

        self.estado = Estado.objects.create(nome="Parana BE12", sigla="PB")
        self.sede = Cidade.objects.create(nome="Curitiba BE12", estado=self.estado)
        self.destino = Cidade.objects.create(nome="Londrina BE12", estado=self.estado)
        self.destino_2 = Cidade.objects.create(nome="Maringa BE12", estado=self.estado)

        # A antecedência decide entre `wizard_documentos` e `wizard_justificativa`; o prazo
        # padrão é 10 dias, então 40 fica folgadamente fora e 2 fica dentro.
        hoje = timezone.localdate()
        self.saida_folgada = hoje + timedelta(days=40)
        self.saida_apertada = hoje + timedelta(days=2)

    # -- fixtures -----------------------------------------------------------

    def _oficio_pronto(self):
        """Ofício com viajantes e transporte preenchidos, parado na Etapa 2."""
        self.client.post(reverse("oficios:novo"))
        oficio = Oficio.objects.order_by("-pk").first()
        self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data={
                "protocolo": "12.345.678-9",
                "motivo": "Motivo BE12",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
                "servidores": [str(self.servidor.pk)],
                "action": "save_continue",
            },
        )
        self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data={
                "porte_transporte_armas": "sim",
                "motorista_modo": Oficio.MOTORISTA_MODO_SERVIDOR,
                "motorista": str(self.motorista.pk),
                "viatura": str(self.viatura.pk),
                "transporte_placa_manual": "",
                "transporte_modelo_manual": "",
                "transporte_combustivel_manual": "",
                "transporte_tipo_manual": "",
                "motorista_manual_nome": "",
                "motorista_oficio_referencia": "",
                "motorista_protocolo_ref": "",
                "action": "save_continue",
            },
        )
        return Oficio.objects.get(pk=oficio.pk)

    def _dados_roteiro(self, *, destino=None, saida=None, acao=None, observacoes=""):
        """Roteiro próprio completo: um trecho de ida mais o retorno.

        O retorno não é um trecho — vai nos campos `retorno_*`, senão
        `_validate_roteiro_state` reprova com "Informe a saída do retorno".
        """
        destino = destino or self.destino
        saida = saida or self.saida_folgada
        volta = saida + timedelta(days=2)
        dados = {
            "roteiro_modo": editor_state_builder.ROTEIRO_MODO_PROPRIO,
            "origem_estado": str(self.estado.pk),
            "origem_cidade": str(self.sede.pk),
            "observacoes": observacoes,
            "quantidade_servidores": "1",
            "retorno_saida_data": volta.isoformat(),
            "retorno_saida_hora": "14:00",
            "retorno_chegada_data": volta.isoformat(),
            "retorno_chegada_hora": "18:00",
            "retorno_tempo_cru_estimado_min": "240",
            "retorno_tempo_adicional_min": "0",
            "retorno_duracao_estimada_min": "240",
            "trecho_0_origem_estado_id": str(self.estado.pk),
            "trecho_0_origem_cidade_id": str(self.sede.pk),
            "trecho_0_destino_estado_id": str(destino.estado_id),
            "trecho_0_destino_cidade_id": str(destino.pk),
            "trecho_0_saida_data": saida.isoformat(),
            "trecho_0_saida_hora": "08:00",
            "trecho_0_chegada_data": saida.isoformat(),
            "trecho_0_chegada_hora": "12:00",
            "trecho_0_tempo_cru_estimado_min": "240",
            "trecho_0_tempo_adicional_min": "0",
            "trecho_0_duracao_estimada_min": "240",
        }
        if acao is not None:
            dados["wizard_action"] = acao
        return dados

    def _dados_reusar(self, roteiro, *, acao=None):
        """Reaproveitar um roteiro salvo, sem alterar nada.

        Sem campos de estrutura no POST, `_build_roteiro_state_from_post` copia o estado
        salvo do `route_state_map` — que é a condição para
        `roteiro_state_equivalente_ao_roteiro` bater e o fluxo vincular sem copiar.
        """
        dados = {
            "roteiro_modo": "EVENTO_EXISTENTE",
            "roteiro_id": str(roteiro.pk),
            "quantidade_servidores": "1",
        }
        if acao is not None:
            dados["wizard_action"] = acao
        return dados

    def _roteiro_salvo(self, *, destino=None, observacoes="salvo"):
        """Um roteiro avulso completo, pelo fluxo avulso — o que o picker oferece."""
        antes = set(Roteiro.all_objects.values_list("pk", flat=True))
        resposta = self.client.post(
            reverse("roteiros:novo"),
            data=self._dados_roteiro(destino=destino, observacoes=observacoes),
        )
        self.assertEqual(resposta.status_code, 302, _mensagens(resposta))
        novos = set(Roteiro.all_objects.values_list("pk", flat=True)) - antes
        self.assertEqual(len(novos), 1)
        return Roteiro.all_objects.get(pk=novos.pop())

    def _salvar_etapa(self, oficio, dados):
        return self.client.post(reverse("oficios:wizard_roteiro", args=[oficio.pk]), data=dados)

    # -- 1 e 2: reaproveitar contra copiar ---------------------------------

    def test_1_reaproveitar_roteiro_equivalente_vincula_sem_criar_copia(self):
        salvo = self._roteiro_salvo()
        oficio = self._oficio_pronto()
        total_antes = Roteiro.all_objects.count()

        resposta = self._salvar_etapa(oficio, self._dados_reusar(salvo))

        self.assertEqual(resposta.status_code, 302, _mensagens(resposta))
        oficio.refresh_from_db()
        self.assertEqual(
            oficio.roteiro_id, salvo.pk, "sem alterações, o ofício aponta para o roteiro escolhido"
        )
        self.assertEqual(
            Roteiro.all_objects.count(), total_antes, "reaproveitar não pode gravar uma cópia"
        )

    def test_2_roteiro_alterado_grava_copia_e_deixa_o_escolhido_intacto(self):
        salvo = self._roteiro_salvo(destino=self.destino, observacoes="original")
        oficio = self._oficio_pronto()
        total_antes = Roteiro.all_objects.count()

        # Mesmo picker, mas com estrutura própria no POST e outro destino: não equivale.
        dados = self._dados_roteiro(destino=self.destino_2, observacoes="alterado")
        dados["roteiro_modo"] = "EVENTO_EXISTENTE"
        dados["roteiro_id"] = str(salvo.pk)
        resposta = self._salvar_etapa(oficio, dados)

        self.assertEqual(resposta.status_code, 302, _mensagens(resposta))
        oficio.refresh_from_db()
        self.assertNotEqual(
            oficio.roteiro_id, salvo.pk, "com alterações, o ofício ganha roteiro próprio"
        )
        self.assertEqual(Roteiro.all_objects.count(), total_antes + 1)
        salvo.refresh_from_db()
        self.assertEqual(
            salvo.observacoes,
            "ORIGINAL",
            "o roteiro escolhido pertence a outros documentos e não pode ser alterado",
        )
        self.assertEqual(
            list(salvo.destinos.values_list("cidade_id", flat=True)), [self.destino.pk]
        )

    def test_3_roteiro_vinculado_nao_rascunho_nao_e_modificado(self):
        """A trava de `route_views.py:137`: só rascunho pode ser reescrito no lugar."""
        compartilhado = self._roteiro_salvo(observacoes="de outro oficio")
        compartilhado.status = Roteiro.STATUS_FINALIZADO
        compartilhado.save(update_fields=["status"])
        oficio = self._oficio_pronto()
        oficio.roteiro = compartilhado
        oficio.save(update_fields=["roteiro"])
        total_antes = Roteiro.all_objects.count()

        resposta = self._salvar_etapa(
            oficio, self._dados_roteiro(destino=self.destino_2, observacoes="tentando reescrever")
        )

        self.assertEqual(resposta.status_code, 302, _mensagens(resposta))
        self.assertEqual(Roteiro.all_objects.count(), total_antes + 1, "materializa rascunho novo")
        oficio.refresh_from_db()
        self.assertNotEqual(oficio.roteiro_id, compartilhado.pk)
        self.assertEqual(oficio.roteiro.status, Roteiro.STATUS_RASCUNHO)
        compartilhado.refresh_from_db()
        self.assertEqual(compartilhado.observacoes, "DE OUTRO OFICIO")
        self.assertEqual(compartilhado.status, Roteiro.STATUS_FINALIZADO)

    # -- 4 e 5: as quatro saídas de navegação do caminho válido ------------

    def test_4_wizard_next_com_antecedencia_folgada_vai_para_documentos(self):
        oficio = self._oficio_pronto()

        resposta = self._salvar_etapa(
            oficio, self._dados_roteiro(saida=self.saida_folgada, acao="wizard_next")
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertIn(
            "Roteiro e diárias salvos. Continue para a próxima etapa quando estiver pronto.",
            _mensagens(resposta),
        )

    def test_4b_wizard_next_com_saida_apertada_vai_para_justificativa(self):
        oficio = self._oficio_pronto()

        resposta = self._salvar_etapa(
            oficio, self._dados_roteiro(saida=self.saida_apertada, acao="wizard_next")
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta.url,
            reverse("oficios:wizard_justificativa", args=[oficio.pk]),
            "dentro do prazo, a justificativa é obrigatória e entra no caminho",
        )

    def test_5_wizard_back_volta_para_dados_viajantes(self):
        oficio = self._oficio_pronto()

        resposta = self._salvar_etapa(oficio, self._dados_roteiro(acao="wizard_back"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertIn("Roteiro e diárias salvos.", _mensagens(resposta))

    def test_5b_save_draft_list_volta_para_a_lista(self):
        oficio = self._oficio_pronto()

        resposta = self._salvar_etapa(oficio, self._dados_roteiro(acao="save_draft_list"))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("oficios:index"), resposta.url)
        self.assertIn("Roteiro e diárias salvos.", _mensagens(resposta))

    def test_5c_acao_desconhecida_recarrega_a_etapa_com_mensagem_propria(self):
        oficio = self._oficio_pronto()

        resposta = self._salvar_etapa(oficio, self._dados_roteiro(acao="save_draft"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertIn("Rascunho do roteiro salvo.", _mensagens(resposta))

    # -- 6: os dois ramos descobertos do soft-advance ----------------------

    def test_6_soft_advance_com_wizard_back_volta_para_dados_viajantes(self):
        oficio = self._oficio_pronto()
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))

        resposta = self._salvar_etapa(
            oficio,
            {
                "wizard_action": "wizard_back",
                "origem_estado": str(self.estado.pk),
                "origem_cidade": str(self.sede.pk),
            },
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertIn("Roteiro incompleto salvo como rascunho.", _mensagens(resposta))
        oficio.refresh_from_db()
        self.assertEqual(oficio.roteiro.status, Roteiro.STATUS_RASCUNHO)

    # -- 7: o GET que pré-seleciona o roteiro do evento --------------------

    def test_7_get_sem_roteiro_pre_seleciona_o_roteiro_padrao_do_evento(self):
        from eventos.models import Evento

        evento = Evento.objects.create(area=area_de_teste(), titulo="EVENTO BE12")
        roteiro_do_evento = self._roteiro_salvo(observacoes="do evento")
        roteiro_do_evento.evento = evento
        roteiro_do_evento.save(update_fields=["evento"])
        oficio = self._oficio_pronto()
        oficio.evento = evento
        oficio.save(update_fields=["evento"])

        resposta = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(
            Oficio.objects.get(pk=oficio.pk).roteiro_id, "pré-selecionar não pode gravar nada"
        )
        self.assertContains(resposta, f'value="{self.sede.pk}"')


class RoteiroDoOficioSemRequestTests(TestCase):
    """`BE-12`: o que só passou a ser testável depois de a regra sair da view.

    Os três cenários abaixo eram inalcançáveis pelo cliente HTTP. O primeiro porque a
    view nunca teve transação; os outros dois porque dependem de condições que o
    caminho HTTP não produz — e essa impossibilidade *era* o defeito catalogado:
    "não é testável sem subir request HTTP nem reusável pelo fluxo avulso".
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="be12_service", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.area = area_de_teste()
        self.estado = Estado.objects.create(nome="Parana SR", sigla="SR")
        self.sede = Cidade.objects.create(nome="Curitiba SR", estado=self.estado)
        self.destino = Cidade.objects.create(nome="Londrina SR", estado=self.estado)
        self.oficio = Oficio.objects.create(area=self.area)
        self.saida = timezone.localdate() + timedelta(days=30)

    def _submissao(self, *, quantidade_servidores=1):
        """Form e estado válidos montados sem passar por view nenhuma."""
        from urllib.parse import urlencode

        from django.http import QueryDict

        from roteiros.forms import RoteiroForm
        from roteiros.services import validar_submissao_editor_roteiro

        volta = self.saida + timedelta(days=2)
        post = QueryDict(
            urlencode(
                {
                    "roteiro_modo": editor_state_builder.ROTEIRO_MODO_PROPRIO,
                    "origem_estado": str(self.estado.pk),
                    "origem_cidade": str(self.sede.pk),
                    "observacoes": "sem request",
                    "quantidade_servidores": str(quantidade_servidores),
                    "retorno_saida_data": volta.isoformat(),
                    "retorno_saida_hora": "14:00",
                    "retorno_chegada_data": volta.isoformat(),
                    "retorno_chegada_hora": "18:00",
                    "retorno_tempo_cru_estimado_min": "240",
                    "retorno_tempo_adicional_min": "0",
                    "retorno_duracao_estimada_min": "240",
                    "trecho_0_origem_estado_id": str(self.estado.pk),
                    "trecho_0_origem_cidade_id": str(self.sede.pk),
                    "trecho_0_destino_estado_id": str(self.estado.pk),
                    "trecho_0_destino_cidade_id": str(self.destino.pk),
                    "trecho_0_saida_data": self.saida.isoformat(),
                    "trecho_0_saida_hora": "08:00",
                    "trecho_0_chegada_data": self.saida.isoformat(),
                    "trecho_0_chegada_hora": "12:00",
                    "trecho_0_tempo_cru_estimado_min": "240",
                    "trecho_0_tempo_adicional_min": "0",
                    "trecho_0_duracao_estimada_min": "240",
                }
            )
        )
        form = RoteiroForm(post)
        roteiro_state, validated, diarias = validar_submissao_editor_roteiro(post, {})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(validated["ok"], validated.get("errors"))
        return post, form, roteiro_state, validated, diarias

    def test_9_fora_de_request_o_roteiro_nasce_na_area_do_oficio(self):
        """`NOVO-88`: antes disto o ramo válido criava `Roteiro(...)` sem `area=`.

        A área saía de `Roteiro.save()` → `get_current_area()`, que fora de request é
        `None` — e o `INSERT` batia no `NOT NULL` do `DB-02`. Pelo HTTP as duas leituras
        coincidiam por acidente (`get_oficio_by_id` lê o mesmo thread-local), então o
        acoplamento era invisível. Aqui ele aparece.
        """
        from core.testing import sem_request
        from oficios.services import salvar_roteiro_do_oficio

        post, form, roteiro_state, validated, diarias = self._submissao()

        with sem_request():
            resultado = salvar_roteiro_do_oficio(
                self.oficio,
                post,
                form,
                roteiro_state=roteiro_state,
                validated=validated,
                diarias_resultado=diarias,
            )

        self.assertTrue(resultado.criou_rascunho)
        self.assertFalse(resultado.reusou_sem_copia)
        self.assertEqual(
            resultado.roteiro.area_id,
            self.oficio.area_id,
            "a área é a do ofício, passada explicitamente — não a ativa da requisição",
        )
        self.oficio.refresh_from_db()
        self.assertEqual(self.oficio.roteiro_id, resultado.roteiro.pk)

    def test_10_duas_pessoas_nao_multiplicam_as_diarias_duas_vezes(self):
        """O editor mostra o total da equipe, mas o roteiro persiste o valor unitário.

        O resumo do ofício é o único ponto que aplica o efetivo. Persistir o total
        mostrado pelo editor faria duas pessoas virarem multiplicador quatro.
        """
        from oficios.services import salvar_roteiro_do_oficio

        cargo = Cargo.objects.create(area=self.area, nome="Cargo diárias unitárias")
        servidores = [
            Servidor.objects.create(
                area=self.area,
                nome=f"Servidor diárias {indice}",
                cargo=cargo,
                cpf=f"1234567890{indice}",
            )
            for indice in (1, 2)
        ]
        self.oficio.servidores.add(*servidores)
        post, form, roteiro_state, validated, diarias_equipe = self._submissao(
            quantidade_servidores=2
        )

        resultado = salvar_roteiro_do_oficio(
            self.oficio,
            post,
            form,
            roteiro_state=roteiro_state,
            validated=validated,
            diarias_resultado=diarias_equipe,
        )

        valor_exibido_equipe = diarias_equipe["totais"]["total_valor_decimal"]
        self.assertGreater(valor_exibido_equipe, 0)
        self.assertEqual(resultado.roteiro.valor_diarias * 2, valor_exibido_equipe)
        self.oficio.refresh_from_db()
        self.assertEqual(
            self.oficio.diarias_para_servidores()["valor_decimal"],
            valor_exibido_equipe,
        )

    def test_8_falha_no_meio_da_gravacao_nao_deixa_roteiro_orfao(self):
        """`atomic`: a requisição grava 4 tabelas, e antes do `BE-12` nenhuma transação
        as unia. Uma falha entre gravar o roteiro e apontar o ofício deixava roteiro
        órfão no banco — o item 1 da lista de perigo do `BE-14`."""
        from unittest.mock import patch

        from oficios import services as oficios_services

        post, form, roteiro_state, validated, diarias = self._submissao()
        antes = Roteiro.all_objects.count()

        with patch.object(
            oficios_services, "_revincular_roteiro_ao_oficio", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                oficios_services.salvar_roteiro_do_oficio(
                    self.oficio,
                    post,
                    form,
                    roteiro_state=roteiro_state,
                    validated=validated,
                    diarias_resultado=diarias,
                )

        self.assertEqual(
            Roteiro.all_objects.count(), antes, "o roteiro gravado antes da falha tem de sumir"
        )
        self.oficio.refresh_from_db()
        self.assertIsNone(self.oficio.roteiro_id)

    def test_10_vincular_roteiro_de_outra_area_e_recusado(self):
        """Inalcançável pela view — `obter_roteiro_escolhido_do_post` já filtra pela área
        do ofício —, então esta guarda nunca tinha sido exercitada."""
        from usuarios.models import AreaTrabalho

        from oficios.services import vincular_roteiro_ao_oficio_sem_copia

        outra = AreaTrabalho.objects.create(sigla="BE12X", nome="Outra area BE12")
        alheio = Roteiro.all_objects.create(area=outra, tipo=Roteiro.TIPO_AVULSO)

        with self.assertRaises(ValueError):
            vincular_roteiro_ao_oficio_sem_copia(self.oficio, alheio)

        self.oficio.refresh_from_db()
        self.assertIsNone(self.oficio.roteiro_id)
