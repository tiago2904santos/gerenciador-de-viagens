"""BE-04 — os pickers de vínculo do evento só podem oferecer documentos da área ativa.

`EventoNovoCadastroForm.__init__` filtra ofícios por área e **não filtra** os
outros quatro vínculos. O efeito não é só de leitura: selecionar um documento
alheio faz `core.tenancy.validate_cross_area_foreign_keys` levantar
`ValidationError` dentro do `pre_save`, o que estoura como 500 em vez de erro de
formulário.

O teste entra pela view para que o middleware resolva a área ativa — instanciar o
form direto não exercita `get_current_area()`.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eventos.models import Evento
from oficios.models import Oficio
from ordens_servico.models import OrdemServico
from planos_trabalho.models import PlanoTrabalho
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea

# (campo do formulário, atributo do registro criado na área alheia)
CAMPOS_DE_VINCULO = [
    "oficios_vinculados",
    "ordens_servico_vinculadas",
    "planos_trabalho_vinculados",
    "termos_vinculados",
    "roteiros_vinculados",
]


class PickersDeVinculoNaoVazamEntreAreasTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        self.user = get_user_model().objects.create_user(username="vinculos", password="123456")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.evento = Evento.objects.create(titulo="Evento da área A", area=self.area)

        # Um registro de cada tipo na área alheia. Nenhum pode aparecer no picker.
        self.alheios = {
            "oficios_vinculados": Oficio.objects.create(numero=901, ano=2026, area=self.outra),
            "ordens_servico_vinculadas": OrdemServico.objects.create(numero=901, ano=2026, area=self.outra),
            "planos_trabalho_vinculados": PlanoTrabalho.objects.create(numero=901, ano=2026, area=self.outra),
            "termos_vinculados": TermoAutorizacao.objects.create(area=self.outra),
            "roteiros_vinculados": Roteiro.objects.create(area=self.outra),
        }
        # E um de cada na área do usuário, para provar que o filtro não zera o picker.
        self.proprios = {
            "oficios_vinculados": Oficio.objects.create(numero=101, ano=2026, area=self.area),
            "ordens_servico_vinculadas": OrdemServico.objects.create(numero=101, ano=2026, area=self.area),
            "planos_trabalho_vinculados": PlanoTrabalho.objects.create(numero=101, ano=2026, area=self.area),
            "termos_vinculados": TermoAutorizacao.objects.create(area=self.area),
            "roteiros_vinculados": Roteiro.objects.create(area=self.area),
        }

    def _form_da_etapa_1(self):
        response = self.client.get(
            reverse("eventos:guiado_etapa", args=[self.evento.pk, 1])
        )
        self.assertEqual(response.status_code, 200)
        return response.context["form"]

    def test_nenhum_picker_oferece_documento_de_outra_area(self):
        form = self._form_da_etapa_1()

        vazando = []
        for campo in CAMPOS_DE_VINCULO:
            queryset = form.fields[campo].queryset
            if queryset.filter(pk=self.alheios[campo].pk).exists():
                vazando.append(campo)

        self.assertEqual(
            vazando,
            [],
            msg=f"pickers oferecendo documento de outra área: {vazando}",
        )

    def test_os_documentos_da_propria_area_continuam_disponiveis(self):
        """O recorte não pode esvaziar o picker — seria trocar um defeito por outro."""
        form = self._form_da_etapa_1()

        faltando = [
            campo
            for campo in CAMPOS_DE_VINCULO
            if not form.fields[campo].queryset.filter(pk=self.proprios[campo].pk).exists()
        ]

        self.assertEqual(faltando, [], msg=f"pickers que perderam o próprio documento: {faltando}")
