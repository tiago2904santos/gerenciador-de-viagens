"""Fixtures compartilhadas dos testes de planos_trabalho."""

from __future__ import annotations

from datetime import date
from datetime import time

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade

from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import PlanoTrabalho
from core.testing import area_de_teste


UNIDADE_ASCOM_NOME = "ASSESSORIA DE COMUNICAÇÃO SOCIAL"
UNIDADE_ASCOM_SIGLA = "ASCOM"


def criar_base_geografica():
    parana = Estado.objects.create(nome="Paraná", sigla="PR")
    curitiba = Cidade.objects.create(estado=parana, nome="Curitiba", capital=True)
    maringa = Cidade.objects.create(estado=parana, nome="Maringá")
    sarandi = Cidade.objects.create(estado=parana, nome="Sarandi")
    return parana, curitiba, maringa, sarandi


def configurar_sistema(curitiba):
    # DB-02: sem área corrente o singleton cai na área técnica `__SISTEMA__`,
    # que diverge da área de teste dos registros e dispara o guarda de FK.
    # A configuração é da área do plano, como em produção.
    config = ConfiguracaoSistema.get_for_area(area_de_teste())
    config.cidade_sede_padrao = curitiba
    config.unidade = Unidade.objects.create(area=area_de_teste(), nome=UNIDADE_ASCOM_NOME, sigla=UNIDADE_ASCOM_SIGLA)
    config.cidade_endereco = "Curitiba"
    config.uf = "PR"
    config.nome_chefia = "João Mário Nunes de Góes"
    config.cargo_chefia = "Assessor de Comunicação Social"
    config.pt_sufixo_numero = "ASCOM"
    config.save()
    # `b970a84` fez o documento resolver o assinante pela ÁREA do registro, com
    # `fallback_geral=False` — `config.nome_chefia` deixou de ser usado como
    # último recurso. Sem uma linha de assinatura, o nome sai vazio. A fixture
    # passou a declarar o assinante de verdade, que é o contrato novo.
    cargo = Cargo.objects.create(area=area_de_teste(), nome="Assessor de Comunicação Social")
    chefia = Servidor.objects.create(area=area_de_teste(), 
        nome="João Mário Nunes de Góes", cpf="98765432100", cargo=cargo
    )
    AssinaturaConfiguracao.objects.create(
        configuracao=config,
        tipo=AssinaturaConfiguracao.PLANO_TRABALHO,
        servidor=chefia,
        ordem=1,
    )
    return config


def criar_plano_maringa(maringa, *, efetivo=6):
    """Plano com os dados do exemplo real 20/2026 (Maringá)."""
    plano = PlanoTrabalho.objects.create(area=area_de_teste(), 
        numero=20,
        ano=2026,
        sufixo_numero="ASCOM",
        destino_estado=maringa.estado,
        destino_cidade=maringa,
        data_evento_inicio=date(2026, 6, 25),
        data_evento_fim=date(2026, 6, 27),
        # 4 pernoites + parcial de 7h (entre 6h e 8h) => 4 x 100% + 1 x 15%
        saida_sede_data=date(2026, 6, 24),
        saida_sede_hora=time(7, 0),
        chegada_sede_data=date(2026, 6, 28),
        chegada_sede_hora=time(14, 0),
    )
    cargo = Cargo.objects.get_or_create(area=area_de_teste(), nome="Policial Civil")[0]
    unidade = Unidade.objects.get_or_create(area=area_de_teste(), 
        nome=UNIDADE_ASCOM_NOME,
        defaults={"sigla": UNIDADE_ASCOM_SIGLA},
    )[0]
    EfetivoPlano.objects.create(plano=plano, unidade=unidade, cargo=cargo, quantidade=efetivo)
    return plano


def criar_servidor(nome="Juliana Villela de Barros", cargo_nome="Papiloscopista"):
    cargo = Cargo.objects.get_or_create(area=area_de_teste(), nome=cargo_nome)[0]
    return Servidor.objects.create(area=area_de_teste(), nome=nome, cargo=cargo)
