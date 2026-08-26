"""`NOVO-20260826-021707-b02175bdd4cd`: documentos do evento herdavam 1 destino.

O evento sempre gravou a lista inteira (`destino_uf`/`destino_cidade` para o
primeiro, `destinos_extras` para o resto) e `build_evento_document_seed` sempre
devolveu tudo em ``destinos``. Quem consumia é que lia só ``cidade``/``estado``:
Ordem de Serviço e Plano de Trabalho (etapa 4) e Termo (etapa 5) abriam com um
destino, e o operador redigitava o que já havia cadastrado na etapa 1.

O roteiro (etapa 2) e o ofício (etapa 3) já liam a lista inteira — os dois casos
ficam congelados aqui para não regredirem junto.
"""

from django.test import TestCase

from cadastros.models import Cidade, Estado
from core.testing import area_de_teste
from eventos.models import Evento
from eventos.services import build_evento_document_seed, destinos_seed_para_formulario


class DestinosDoEventoNosDocumentosTests(TestCase):
    def setUp(self):
        self.area = area_de_teste()
        self.parana = Estado.objects.create(sigla="PR", nome="Parana")
        self.curitiba = Cidade.objects.create(nome="CURITIBA", estado=self.parana, uf="PR")
        self.londrina = Cidade.objects.create(nome="LONDRINA", estado=self.parana, uf="PR")
        self.evento = Evento.objects.create(
            area=self.area,
            titulo="Evento com dois destinos",
            destino_uf="PR",
            destino_cidade="CURITIBA",
            destinos_extras=[{"uf": "PR", "cidade": "LONDRINA"}],
        )

    def _seed(self):
        return build_evento_document_seed(self.evento)

    def test_o_evento_guarda_os_dois_destinos(self):
        seed = self._seed()

        self.assertEqual(
            [cidade.nome for cidade, _estado in seed["destinos"]],
            ["CURITIBA", "LONDRINA"],
        )
        self.assertEqual(
            destinos_seed_para_formulario(seed),
            [(self.parana.pk, self.curitiba.pk), (self.parana.pk, self.londrina.pk)],
        )

    def test_helper_ignora_destino_sem_cidade_resolvida(self):
        """Cidade apagada do cadastro não pode virar linha meia-boca no formulário."""
        self.evento.destinos_extras = [{"uf": "PR", "cidade": "CIDADE QUE NAO EXISTE"}]
        self.evento.save(update_fields=["destinos_extras"])

        self.assertEqual(
            destinos_seed_para_formulario(self._seed()),
            [(self.parana.pk, self.curitiba.pk)],
        )

    def test_etapa4_ordem_de_servico_abre_com_os_dois(self):
        from ordens_servico.forms import OrdemServicoForm
        from ordens_servico.models import OrdemServico

        seed = self._seed()
        form = OrdemServicoForm(
            instance=OrdemServico(evento=self.evento),
            initial={
                "destino_estado": seed["estado"].pk,
                "destino_cidade": seed["cidade"].pk,
                "destinos_seed": destinos_seed_para_formulario(seed),
            },
        )

        self.assertEqual(
            [(linha["estado_id"], linha["cidade_id"]) for linha in form.destination_rows],
            [(str(self.parana.pk), str(self.curitiba.pk)), (str(self.parana.pk), str(self.londrina.pk))],
        )

    def test_etapa4_plano_de_trabalho_nasce_com_os_dois(self):
        from planos_trabalho.services import criar_plano_rascunho

        plano = criar_plano_rascunho(self.evento)

        self.assertEqual(
            [
                (destino.ordem, destino.cidade.nome)
                for destino in plano.destinos.filter(evento__isnull=True).order_by("ordem")
            ],
            [(1, "CURITIBA"), (2, "LONDRINA")],
        )
        # O campo legado continua apontando para o primeiro, como o resto do app espera.
        self.assertEqual(plano.destino_cidade_id, self.curitiba.pk)

    def test_etapa5_termo_abre_com_os_dois(self):
        from termos.forms import TermoAutorizacaoForm
        from termos.models import TermoAutorizacao

        seed = self._seed()
        form = TermoAutorizacaoForm(
            instance=TermoAutorizacao(
                evento=self.evento,
                destino_estado=seed.get("estado"),
                destino_cidade=seed.get("cidade"),
            ),
            initial={
                "destino_estado": seed["estado"].pk,
                "destino_cidade": seed["cidade"].pk,
                "destinos_seed": destinos_seed_para_formulario(seed),
            },
        )

        self.assertEqual(
            [(linha["estado_id"], linha["cidade_id"]) for linha in form.destination_rows],
            [(str(self.parana.pk), str(self.curitiba.pk)), (str(self.parana.pk), str(self.londrina.pk))],
        )

    def test_evento_de_destino_unico_continua_com_uma_linha(self):
        """Sem `destinos_seed`, nada muda para quem tem um destino só."""
        from ordens_servico.forms import OrdemServicoForm
        from ordens_servico.models import OrdemServico
        from planos_trabalho.services import criar_plano_rascunho

        self.evento.destinos_extras = []
        self.evento.save(update_fields=["destinos_extras"])
        seed = self._seed()

        form = OrdemServicoForm(
            instance=OrdemServico(evento=self.evento),
            initial={"destino_estado": seed["estado"].pk, "destino_cidade": seed["cidade"].pk},
        )
        plano = criar_plano_rascunho(self.evento)

        self.assertEqual(len(form.destination_rows), 1)
        self.assertEqual(plano.destinos.filter(evento__isnull=True).count(), 0)
        self.assertEqual(plano.destino_cidade_id, self.curitiba.pk)

    def test_etapa2_roteiro_e_etapa3_oficio_ja_liam_a_lista_inteira(self):
        from oficios.services import criar_oficio_rascunho, montar_roteiro_inicial_do_oficio
        from roteiros.services import montar_initial_roteiro_evento_sem_datas

        initial = montar_initial_roteiro_evento_sem_datas(self.evento)
        _form, destinos_atuais, _trechos, _state = montar_roteiro_inicial_do_oficio(
            criar_oficio_rascunho(self.evento)
        )

        self.assertEqual(
            [(d["estado_id"], d["cidade_id"]) for d in initial["destinos_atuais"]],
            [(self.parana.pk, self.curitiba.pk), (self.parana.pk, self.londrina.pk)],
        )
        self.assertEqual(
            [(d["estado_id"], d["cidade_id"]) for d in destinos_atuais],
            [(self.parana.pk, self.curitiba.pk), (self.parana.pk, self.londrina.pk)],
        )
