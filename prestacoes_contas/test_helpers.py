"""Fixtures reutilizáveis para as fatias de testes de prestações de contas."""

import io
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.tenancy import AREA_SESSION_KEY

from cadastros.models import Cargo
from cadastros.models import Servidor
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


def imagem_bytes(formato="PNG"):
    """Imagem 1×1 de verdade, gerada pelo Pillow.

    Existe porque `core.uploads.validate_private_document_upload` abre e verifica o
    arquivo: cabeçalho truncado (`b"\\x89PNG\\r\\n\\x1a\\n"`) passava enquanto a política
    não rodava (QA-04) e agora é recusado — com razão. Teste de "aceita PNG" precisa
    enviar um PNG.
    """
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buffer, format=formato)
    return buffer.getvalue()


PDF_MINIMO = b"%PDF-1.4\n%%EOF\n"


@dataclass(frozen=True)
class PrestacaoFixture:
    area: AreaTrabalho
    oficio: Oficio
    prestacao: PrestacaoContas
    servidores: tuple[Servidor, ...]
    prestacoes_servidor: tuple
    roteiro: Roteiro | None


class PrestacaoFixturesMixin:
    """Fábrica mínima compartilhável pelas seis fatias de T-01."""

    def setUpPrestacaoFixtures(self):
        self.user = get_user_model().objects.create_user(
            username="tester_prestacao_listagem",
            password="123456",
        )
        self.client.force_login(self.user)
        self.area = AreaTrabalho.objects.create(nome="Área Alfa", sigla="ALFA")
        self.outra_area = AreaTrabalho.objects.create(nome="Área Beta", sigla="BETA")
        # Vínculo real, não mock: é ele que o middleware resolve em
        # resolve_area_for_request e grava na sessão. Sem isso, a asserção de
        # isolamento provaria só que o selector filtra — não que a requisição
        # chega com a área certa, que é onde um vazamento entre áreas apareceria.
        VinculoUsuarioArea.objects.create(
            usuario=self.user, area=self.area, area_padrao=True, ativo=True
        )
        self._cargos = {}
        self._cpf_sequence = 0

    def vincular_usuario(self, area, *, padrao=False):
        """Dá ao usuário de teste acesso a outra área (para trocar de área)."""
        return VinculoUsuarioArea.objects.create(
            usuario=self.user, area=area, area_padrao=padrao, ativo=True
        )

    def criar_servidor(self, nome, *, area=None):
        area = area or self.area
        cargo = self._cargos.get(area.pk)
        if cargo is None:
            cargo = Cargo.objects.create(nome=f"Agente {area.sigla}", area=area)
            self._cargos[area.pk] = cargo
        self._cpf_sequence += 1
        return Servidor.objects.create(
            nome=nome,
            cargo=cargo,
            cpf=f"{self._cpf_sequence:011d}",
            area=area,
        )

    def criar_prestacao(
        self,
        *,
        numero,
        ano=2026,
        area=None,
        servidor=None,
        servidores=None,
        status="pendente",
        data_liberacao_diarias: date | None = None,
        arquivada=False,
        finalizada=False,
        cancelado=False,
        criado_em: datetime | None = None,
        com_roteiro=True,
        trechos_roteiro=1,
    ):
        area = area or self.area
        if servidores is None:
            servidores = (servidor or self.criar_servidor(f"Servidor {numero}", area=area),)
        else:
            servidores = tuple(servidores)

        roteiro = None
        if com_roteiro:
            roteiro = Roteiro.objects.create(area=area)
            for ordem in range(trechos_roteiro):
                RoteiroTrecho.objects.create(
                    roteiro=roteiro,
                    tipo=RoteiroTrecho.TIPO_IDA,
                    ordem=ordem,
                )

        oficio = Oficio.objects.create(
            area=area,
            numero=numero,
            ano=ano,
            protocolo=f"{area.pk:02d}{ano}{numero:05d}",
            roteiro=roteiro,
        )
        oficio.servidores.add(*servidores)
        prestacao = PrestacaoContas.objects.get(oficio=oficio)
        if cancelado:
            Oficio.objects.filter(pk=oficio.pk).update(cancelado=True)
            oficio.refresh_from_db()
        if criado_em is not None:
            PrestacaoContas.objects.filter(pk=prestacao.pk).update(criado_em=criado_em)
            prestacao.refresh_from_db()

        prestacoes_servidor = tuple(
            prestacao.servidores_prestacao.filter(servidor__in=servidores).order_by("pk")
        )
        for ps in prestacoes_servidor:
            ps.status = status
            ps.data_liberacao_diarias = data_liberacao_diarias
            ps.arquivada = arquivada
            ps.finalizada = finalizada
            ps.save(
                update_fields=[
                    "status",
                    "data_liberacao_diarias",
                    "arquivada",
                    "finalizada",
                    "atualizado_em",
                ]
            )

        return PrestacaoFixture(
            area=area,
            oficio=oficio,
            prestacao=prestacao,
            servidores=servidores,
            prestacoes_servidor=prestacoes_servidor,
            roteiro=roteiro,
        )

    def get_listagem(self, *, area=None, **params):
        """GET na listagem pelo caminho real: sessão → middleware → selector.

        Trocar de área é trocar a chave da sessão, que é o que a tela de seleção
        de área faz. Nada de mock: o objetivo é justamente exercitar a cadeia
        que isola os dados entre áreas.
        """
        if area is not None and area.pk != self.area.pk:
            sessao = self.client.session
            sessao[AREA_SESSION_KEY] = area.pk
            sessao.save()
        return self.client.get(reverse("prestacoes_contas:index"), params)
