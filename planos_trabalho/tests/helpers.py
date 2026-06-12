"""Fixtures compartilhadas dos testes de planos_trabalho."""

from __future__ import annotations

from datetime import date
from datetime import time

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor

from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import PlanoTrabalho


def criar_base_geografica():
    parana = Estado.objects.create(nome="Paraná", sigla="PR")
    curitiba = Cidade.objects.create(estado=parana, nome="Curitiba", capital=True)
    maringa = Cidade.objects.create(estado=parana, nome="Maringá")
    sarandi = Cidade.objects.create(estado=parana, nome="Sarandi")
    return parana, curitiba, maringa, sarandi


def configurar_sistema(curitiba):
    config = ConfiguracaoSistema.get_singleton()
    config.cidade_sede_padrao = curitiba
    config.unidade = "Assessoria de Comunicação Social"
    config.cidade_endereco = "Curitiba"
    config.uf = "PR"
    config.nome_chefia = "João Mário Nunes de Góes"
    config.cargo_chefia = "Assessor de Comunicação Social"
    config.pt_sufixo_numero = "ASCOM"
    config.save()
    return config


def criar_plano_maringa(maringa, *, efetivo=6):
    """Plano com os dados do exemplo real 20/2026 (Maringá)."""
    plano = PlanoTrabalho.objects.create(
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
    cargo = Cargo.objects.get_or_create(nome="Policial Civil")[0]
    EfetivoPlano.objects.create(plano=plano, cargo=cargo, quantidade=efetivo)
    return plano


def criar_servidor(nome="Juliana Villela de Barros", cargo_nome="Papiloscopista"):
    cargo = Cargo.objects.get_or_create(nome=cargo_nome)[0]
    return Servidor.objects.create(nome=nome, cargo=cargo)
