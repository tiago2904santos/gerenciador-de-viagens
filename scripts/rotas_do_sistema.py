#!/usr/bin/env python
"""Corpus canônico das 43 telas vivas usadas pelas réguas do frontend.

O catálogo anterior morava ao lado de screenshots que serão removidos pelo
BE-24 e ainda continha quatorze rotas do UI Lab apagado. Os IDs abaixo apontam
para o primeiro registro criado por ``resetar_banco_demo`` no banco efêmero das
medições. O corpus não cria dados nem abre o navegador; os medidores são os
donos dessas duas responsabilidades.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RotaSistema:
    slug: str
    path: str
    requires_auth: bool = True


OFICIO_PK = 1
ROTEIRO_PK = 1
SERVIDOR_PK = 1
VIATURA_PK = 1
JUSTIFICATIVA_PK = 1
UNIDADE_PK = 1
CARGO_PK = 1
COMBUSTIVEL_PK = 1
MODELO_MOTIVO_PK = 1

ROTAS = (
    RotaSistema("login", "/login/", requires_auth=False),
    RotaSistema("dashboard", "/"),
    RotaSistema("oficios-lista", "/oficios/"),
    RotaSistema("oficios-novo", "/oficios/novo/"),
    RotaSistema("oficios-detalhe", f"/oficios/{OFICIO_PK}/"),
    RotaSistema("oficios-editar", f"/oficios/{OFICIO_PK}/editar/"),
    RotaSistema("oficios-wizard-dados-viajantes", f"/oficios/{OFICIO_PK}/dados-viajantes/"),
    RotaSistema("oficios-wizard-transporte", f"/oficios/{OFICIO_PK}/transporte/"),
    RotaSistema("oficios-wizard-roteiro", f"/oficios/{OFICIO_PK}/roteiro/"),
    RotaSistema("oficios-wizard-justificativa", f"/oficios/{OFICIO_PK}/justificativa/"),
    RotaSistema("oficios-wizard-resumo", f"/oficios/{OFICIO_PK}/resumo/"),
    RotaSistema("oficios-wizard-documentos", f"/oficios/{OFICIO_PK}/documentos/"),
    # A lista antiga apontava para /oficios/<pk>/assinaturas/, removida. Eventos
    # não estava representado no corpus, apesar de ser um domínio vivo.
    RotaSistema("eventos-lista", "/eventos/"),
    RotaSistema("oficios-modelos-motivo-lista", "/oficios/modelos-motivo/"),
    RotaSistema("oficios-modelos-motivo-novo", "/oficios/modelos-motivo/novo/"),
    RotaSistema(
        "oficios-modelos-motivo-editar",
        f"/oficios/modelos-motivo/{MODELO_MOTIVO_PK}/editar/",
    ),
    RotaSistema("roteiros-lista", "/roteiros/"),
    RotaSistema("roteiros-novo", "/roteiros/novo/"),
    # Roteiro não tem mais tela de detalhe separada; a edição é a tela canônica.
    # A vaga passa à lista de prestações, também ausente no catálogo antigo.
    RotaSistema("prestacoes-contas-lista", "/prestacoes-contas/"),
    RotaSistema("roteiros-editar", f"/roteiros/{ROTEIRO_PK}/editar/"),
    RotaSistema("termos-lista", "/termos/"),
    RotaSistema("termos-preview-oficio", f"/termos/oficio/{OFICIO_PK}/preview/"),
    RotaSistema("justificativas-lista", "/justificativas/"),
    RotaSistema("justificativas-novo", "/justificativas/novo/"),
    RotaSistema("justificativas-editar", f"/justificativas/{JUSTIFICATIVA_PK}/editar/"),
    RotaSistema("planos-trabalho-lista", "/planos-trabalho/"),
    RotaSistema("ordens-servico-lista", "/ordens-servico/"),
    RotaSistema("configuracao", "/cadastros/configuracao/"),
    RotaSistema("servidores-lista", "/cadastros/servidores/"),
    RotaSistema("servidor-novo", "/cadastros/servidores/novo/"),
    RotaSistema("servidor-editar", f"/cadastros/servidores/{SERVIDOR_PK}/editar/"),
    RotaSistema("viaturas-lista", "/cadastros/viaturas/"),
    RotaSistema("viatura-nova", "/cadastros/viaturas/nova/"),
    RotaSistema("viatura-editar", f"/cadastros/viaturas/{VIATURA_PK}/editar/"),
    RotaSistema("unidades-lista", "/cadastros/unidades/"),
    RotaSistema("unidade-nova", "/cadastros/unidades/nova/"),
    RotaSistema("unidade-editar", f"/cadastros/unidades/{UNIDADE_PK}/editar/"),
    RotaSistema("cargos-lista", "/cadastros/cargos/"),
    RotaSistema("cargo-novo", "/cadastros/cargos/novo/"),
    RotaSistema("cargo-editar", f"/cadastros/cargos/{CARGO_PK}/editar/"),
    RotaSistema("combustiveis-lista", "/cadastros/combustiveis/"),
    RotaSistema("combustivel-novo", "/cadastros/combustiveis/novo/"),
    RotaSistema("combustivel-editar", f"/cadastros/combustiveis/{COMBUSTIVEL_PK}/editar/"),
)


def main() -> int:
    for rota in ROTAS:
        acesso = "autenticada" if rota.requires_auth else "pública"
        print(f"{rota.slug:42} {acesso:11} {rota.path}")
    print(f"\nTotal: {len(ROTAS)} rotas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
