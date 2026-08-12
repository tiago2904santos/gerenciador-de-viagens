#!/usr/bin/env python
"""PF-07 — régua de desempenho das listas, com volume de verdade.

## Por que este script existe

A medição de linha de base de 08/2026 mediu seis domínios **com o banco vazio**:
Termos, Prestações, Eventos, Planos de Trabalho, Ordens de Serviço e
Justificativas responderam em ~1 ms com zero linha. Aqueles números não valem
nada, e o ciclo anterior tinha registrado que **Termos emitia 54 consultas por
página** — correção nunca confirmada.

Sem régua, toda etapa de desempenho é afirmação sem prova, e a regressão volta no
PR seguinte sem ninguém ver (`docs/PLANO_DESEMPENHO.md`, Etapa D1).

## O que ele mede

Para cada rota de lista, em **dois volumes** (200 e 20.000 registros por domínio):

- **consultas** por requisição — o detector de N+1, e o número que o `PF-07`
  nomeia;
- **KB de HTML** da resposta — o número que o `PF-01` (folha de ícones) precisa;
- **tempo** de resposta, mediana de N repetições.

O volume grande é distribuído entre **três áreas de trabalho**, com só um terço
na área ativa. Não é detalhe: a medição de base mostrou que o custo cresce com a
tabela inteira, não com a fatia do usuário — cada área paga pelo volume das
outras. Semear tudo na área ativa esconderia exatamente esse efeito.

## O que ele reprova no CI

`consultas` e `kb_html` têm teto por rota e por volume, em
`scripts/tetos_desempenho.json`. Passou do teto, sai 1.

**Tempo não tem teto.** Não é esquecimento: é medido, é impresso e vai para o
JSON de saída, mas não reprova. Num runner compartilhado a variação de relógio é
grande o bastante para que um teto útil não pegue nada e um teto apertado
reprove por ruído — este repositório já pagou essa conta, com o *benchmark* do
unoserver reprovando três vezes seguidas por aquecimento, inclusive na `main`
(ver o comentário do passo em `tests.yml`). Consulta e byte são determinísticos e
detectam as mesmas regressões estruturais; tempo entra como diagnóstico para quem
está lendo o relatório, não como catraca.

## Uso

    python scripts/medir_desempenho.py                      # os dois volumes, com teto
    python scripts/medir_desempenho.py --volumes 200         # só o rápido
    python scripts/medir_desempenho.py --json medicao.json   # salva o relatório
    python scripts/medir_desempenho.py --atualizar-tetos     # regrava os tetos medidos

`--atualizar-tetos` é para pessoas, não para o CI: ele **regrava** o arquivo de
tetos com o que acabou de medir. Catraca só desce, e o comando **recusa subir** um
teto: se a medição piorou, ele mantém o valor antigo, imprime o que subiria e
manda usar `--permitir-subir-teto`. Sem essa guarda, o jeito mais fácil de apagar
uma regressão seria rodar o comando que existe para registrar melhora.

O script cria e destrói o próprio banco de teste; não toca em banco de trabalho.

**Exige PostgreSQL.** `config.settings.test` cai em SQLite em memória quando
`TEST_USE_POSTGRES` não está ligado, e régua de desempenho em SQLite é pior que
régua nenhuma: contagem de consulta e tamanho de HTML até coincidem, mas tempo e
plano de consulta não têm relação com o que produção faz. O script recusa rodar
fora do Postgres em vez de imprimir número que não vale.

    TEST_USE_POSTGRES=true python scripts/medir_desempenho.py
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from datetime import datetime
from datetime import time as dtime
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django  # noqa: E402  (precisa do sys.path e do env acima)

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.test.utils import teardown_test_environment  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.crypto import get_random_string  # noqa: E402

ARQUIVO_TETOS = RAIZ / "scripts" / "tetos_desempenho.json"


def exigir_postgres():
    vendor = connection.vendor
    if vendor == "postgresql":
        return
    raise SystemExit(
        f"Este script mede desempenho e o banco configurado é `{vendor}`, não PostgreSQL.\n"
        "Tempo e plano de consulta em SQLite não têm relação com produção — medir aqui\n"
        "produziria número que parece medição e não é.\n\n"
        "    TEST_USE_POSTGRES=true python scripts/medir_desempenho.py\n\n"
        "(no CI as variáveis DB_* do job já estão definidas; ver tests.yml)"
    )

# Semente fixa: duas execuções da régua têm que dar o mesmo número, senão o teto
# não significa nada.
SEMENTE = 20260805

# ── Tamanho das tabelas de dimensão (`NOVO-50`) ──────────────────────────────
# Elas não crescem com o `--volumes`: são o cadastro, não o movimento. Mas o
# tamanho delas decide o plano de consulta, então tem de ser o de produção.
#: As siglas reais: `Estado.sigla` é `varchar(2)`, então gerar "E00" não cabe —
#: e uma lista inventada de duas letras teria a mesma distribuição de trigramas
#: que a de verdade só por acaso.
SIGLAS_UF = (
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO"
).split()
MUNICIPIOS = 5_570
#: Órgão estadual de porte médio. O número exato importa menos que a ordem de
#: grandeza: com centenas de milhares o planner indexa, com dezenas ele varre.
SERVIDORES = 3_000


def _dt(dia, hora=8):
    """Datetime com fuso a partir de `_data(dia)` — `USE_TZ` está ligado."""
    return timezone.make_aware(datetime.combine(_data(dia), dtime(hora, 0)))


# Toda data semeada cai **no futuro**. Não é enfeite: a aba padrão de todas as
# listas é `futuras` (`core/documento_abas.py:ABA_PADRAO`), que filtra por
# `data >= hoje`. Com datas espalhadas em volta de hoje, a página 1 do volume 200
# vinha com meia dúzia de linhas em vez de encher — e a diferença entre os dois
# volumes passava a medir *quantas linhas a página tem*, não o tamanho do banco.
# Um dia por registro, ciclando em 300, para as datas não serem todas iguais.
def _data(dia):
    return timezone.localdate() + timedelta(days=1 + (dia % 300))


# ── Rotas medidas ────────────────────────────────────────────────────────────
# Só listas: são as telas que crescem com o banco. O painel entra porque agrega
# contagem de vários domínios e é a primeira tela de toda sessão.
ROTAS = [
    ("core:dashboard", "painel"),
    ("oficios:index", "oficios"),
    ("roteiros:index", "roteiros"),
    ("termos:index", "termos"),
    ("eventos:index", "eventos"),
    ("planos_trabalho:index", "planos_trabalho"),
    ("ordens_servico:index", "ordens_servico"),
    ("justificativas:index", "justificativas"),
    ("prestacoes_contas:index", "prestacoes_contas"),
]

# Cenários da mesma rota cuja consulta muda de forma material com parâmetros.
# A busca de Termos merece uma linha própria: foi justamente a rota sem `q` da
# régua que deixou o `DB-11` parecer coberto enquanto a busca levava ~1,8 s.
# A chave é deliberadamente diferente do nome reversível para ter teto próprio.
CENARIOS_COM_QUERY = [
    ("termos:index:busca", "termos:index", "termos_busca", {"q": "137"}),
]


# ── Semeadura ────────────────────────────────────────────────────────────────


def _fatiar_por_area(total, areas):
    """Um terço na área ativa, o resto dividido entre as outras.

    A área ativa é `areas[0]`. Devolve uma lista de tamanho `total` com a área de
    cada registro, para o chamador usar direto no `bulk_create`.
    """
    na_ativa = max(1, total // 3)
    resto = total - na_ativa
    outras = areas[1:] or areas
    return [areas[0]] * na_ativa + [outras[i % len(outras)] for i in range(resto)]


class Semeador:
    """Cria o grafo de dados de cada domínio no volume pedido.

    Tudo em `bulk_create`, inclusive as tabelas intermediárias de M2M: com 20.000
    registros por domínio, uma inserção por linha levaria minutos e o script
    deixaria de caber no CI.
    """

    def __init__(self, volume):
        self.volume = volume
        self.rng = random.Random(SEMENTE)

    # -- base compartilhada ---------------------------------------------------

    def semear_base(self):
        from cadastros.models import Cargo
        from cadastros.models import Cidade
        from cadastros.models import Combustivel
        from cadastros.models import Estado
        from cadastros.models import Servidor
        from cadastros.models import Unidade
        from cadastros.models import Viatura
        from usuarios.models import AreaTrabalho
        from usuarios.models import VinculoUsuarioArea

        self.areas = AreaTrabalho.objects.bulk_create(
            [AreaTrabalho(nome=f"Área {i}", sigla=f"AR{i}") for i in range(3)]
        )
        self.area = self.areas[0]

        # Sem senha literal: o cliente entra por `force_login`, e este usuário vive
        # num banco de teste que o script destrói no fim. Um literal aqui seria
        # indistinguível de credencial de verdade para o leitor e para o scanner
        # de segredo — vale o mesmo raciocínio do `S-01` e do que já está anotado
        # no passo de `check --deploy` do `tests.yml`.
        self.user = get_user_model().objects.create_user(username="regua_desempenho")
        self.user.set_password(get_random_string(24))
        self.user.save(update_fields=["password"])
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)

        # `NOVO-50`: as tabelas de dimensão têm de ter tamanho de produção, não
        # tamanho de conveniência. Com 5 estados e 50 cidades, o planner escolhia
        # varredura sequencial nelas **com razão** — e qualquer medição de índice
        # de texto ou de `select_related` sobre elas dizia o contrário do que
        # diria em produção. Foi o que invalidou a medição do `DB-11` (`pg_trgm`
        # dava 1,03x porque `cadastros_servidor` tinha 100 linhas) e o que deixou
        # o `NOVO-50` em aberto ao medir o `DB-10`.
        #
        # Os números são os do país: 27 unidades federativas e 5.570 municípios.
        self.estados = Estado.objects.bulk_create(
            [Estado(nome=f"Estado {sigla}", sigla=sigla) for sigla in SIGLAS_UF]
        )
        self.cidades = Cidade.objects.bulk_create(
            [
                Cidade(
                    estado=self.estados[i % len(self.estados)],
                    nome=f"Cidade {i:04d}",
                    uf=self.estados[i % len(self.estados)].sigla,
                    capital=(i % 206 == 0),
                )
                for i in range(MUNICIPIOS)
            ]
        )
        self.cargos = Cargo.objects.bulk_create([Cargo(nome=f"Cargo {i}") for i in range(5)])
        self.unidades = Unidade.objects.bulk_create([Unidade(nome=f"Unidade {i}") for i in range(5)])
        self.combustiveis = Combustivel.objects.bulk_create(
            [Combustivel(nome=f"Combustível {i}") for i in range(3)]
        )
        self.viaturas = Viatura.objects.bulk_create(
            [Viatura(placa=f"REG{i:04d}", modelo=f"Modelo {i}") for i in range(10)]
        )
        # `NOVO-50`: eram 100, com a justificativa de que "as listas mostram no
        # máximo algumas dezenas por página". Verdade para renderização, falso
        # para plano de consulta: `Servidor.nome` é buscado por `icontains` em
        # cinco domínios, e com 100 linhas o planner varre sequencialmente por ser
        # mais barato — escondendo o custo que a mesma busca tem em produção.
        self.servidores = Servidor.objects.bulk_create(
            [
                Servidor(
                    nome=f"Servidor {i:05d}",
                    cargo=self.cargos[i % len(self.cargos)],
                    unidade=self.unidades[i % len(self.unidades)],
                )
                for i in range(SERVIDORES)
            ]
        )

    def _servidor(self, i):
        return self.servidores[i % len(self.servidores)]

    def _cidade(self, i):
        return self.cidades[i % len(self.cidades)]

    def _estado(self, i):
        return self.estados[i % len(self.estados)]

    # -- domínios -------------------------------------------------------------

    def semear_eventos(self):
        from eventos.models import Evento
        from eventos.models import TipoEvento

        tipos = TipoEvento.objects.bulk_create([TipoEvento(nome=f"Tipo {i}") for i in range(5)])
        areas = _fatiar_por_area(self.volume, self.areas)

        self.eventos = Evento.objects.bulk_create(
            [
                Evento(
                    area=areas[i],
                    titulo=f"Evento {i:06d} de treinamento e operação conjunta",
                    descricao="Descrição do evento com texto suficiente para a lista.",
                    destino_uf=self._estado(i).sigla,
                    destino_cidade=self._cidade(i).nome,
                    data_inicio=_data(i),
                    data_fim=_data(i) + timedelta(days=2),
                    unidade_responsavel=self.unidades[i % len(self.unidades)],
                    responsavel=self._servidor(i),
                )
                for i in range(self.volume)
            ]
        )
        Evento.tipos.through.objects.bulk_create(
            [
                Evento.tipos.through(evento_id=evento.pk, tipoevento_id=tipos[i % len(tipos)].pk)
                for i, evento in enumerate(self.eventos)
            ]
        )

    def semear_roteiros(self):
        from roteiros.models import Roteiro
        from roteiros.models import RoteiroDestino
        from roteiros.models import RoteiroTrecho

        areas = _fatiar_por_area(self.volume, self.areas)

        self.roteiros = Roteiro.objects.bulk_create(
            [
                Roteiro(
                    area=areas[i],
                    origem_estado=self._estado(i),
                    origem_cidade=self._cidade(i),
                    saida_dt=_dt(i),
                    chegada_dt=_dt(i, 14),
                    evento=self.eventos[i % len(self.eventos)] if self.eventos else None,
                )
                for i in range(self.volume)
            ]
        )
        # Dois destinos e dois trechos por roteiro: é o que faz um N+1 de destino
        # aparecer na contagem em vez de ficar escondido atrás de roteiro vazio.
        RoteiroDestino.objects.bulk_create(
            [
                RoteiroDestino(
                    roteiro=roteiro,
                    estado=self._estado(i + d),
                    cidade=self._cidade(i + d),
                    ordem=d,
                )
                for i, roteiro in enumerate(self.roteiros)
                for d in range(2)
            ]
        )
        RoteiroTrecho.objects.bulk_create(
            [
                RoteiroTrecho(
                    roteiro=roteiro,
                    ordem=t,
                    origem_estado=self._estado(i + t),
                    origem_cidade=self._cidade(i + t),
                    destino_estado=self._estado(i + t + 1),
                    destino_cidade=self._cidade(i + t + 1),
                    saida_dt=_dt(i, 8 + t),
                    chegada_dt=_dt(i, 11 + t),
                )
                for i, roteiro in enumerate(self.roteiros)
                for t in range(2)
            ]
        )

    def semear_oficios(self):
        from oficios.models import Oficio

        areas = _fatiar_por_area(self.volume, self.areas)
        self.oficios = Oficio.objects.bulk_create(
            [
                Oficio(
                    area=areas[i],
                    numero=i + 1,
                    ano=2026,
                    data_criacao=_data(i),
                    protocolo=f"{i:03d}.{i % 1000:03d}.{i % 100:03d}-{i % 10}",
                    assunto=f"Ofício {i:06d} — deslocamento para atividade externa",
                    motivo="Motivo do deslocamento com texto representativo.",
                    evento=self.eventos[i % len(self.eventos)] if self.eventos else None,
                    roteiro=self.roteiros[i] if self.roteiros else None,
                    solicitante=self.unidades[i % len(self.unidades)],
                    viatura=self.viaturas[i % len(self.viaturas)],
                    motorista=self._servidor(i),
                )
                for i in range(self.volume)
            ]
        )
        # Três servidores por ofício: a lista resolve a equipe de cada linha.
        Oficio.servidores.through.objects.bulk_create(
            [
                Oficio.servidores.through(oficio_id=oficio.pk, servidor_id=self._servidor(i + s).pk)
                for i, oficio in enumerate(self.oficios)
                for s in range(3)
            ]
        )

    def semear_termos(self):
        from termos.models import TermoAutorizacao

        areas = _fatiar_por_area(self.volume, self.areas)
        self.termos = TermoAutorizacao.objects.bulk_create(
            [
                TermoAutorizacao(
                    area=areas[i],
                    evento=self.eventos[i % len(self.eventos)] if self.eventos else None,
                    oficio=self.oficios[i] if self.oficios else None,
                    destino_estado=self._estado(i),
                    destino_cidade=self._cidade(i),
                    data_evento_inicio=_data(i),
                    data_evento_fim=_data(i) + timedelta(days=2),
                    viatura=self.viaturas[i % len(self.viaturas)],
                )
                for i in range(self.volume)
            ]
        )
        TermoAutorizacao.servidores.through.objects.bulk_create(
            [
                TermoAutorizacao.servidores.through(
                    termoautorizacao_id=termo.pk, servidor_id=self._servidor(i + s).pk
                )
                for i, termo in enumerate(self.termos)
                for s in range(3)
            ]
        )

    def semear_planos(self):
        from planos_trabalho.models import PlanoDestino
        from planos_trabalho.models import PlanoTrabalho
        from planos_trabalho.models import ProgramaSolicitante

        programas = ProgramaSolicitante.objects.bulk_create(
            [ProgramaSolicitante(nome=f"Programa {i}") for i in range(5)]
        )
        areas = _fatiar_por_area(self.volume, self.areas)
        planos = PlanoTrabalho.objects.bulk_create(
            [
                PlanoTrabalho(
                    area=areas[i],
                    numero=i + 1,
                    ano=2026,
                    data_criacao=_data(i),
                    evento=self.eventos[i % len(self.eventos)] if self.eventos else None,
                    programa=programas[i % len(programas)],
                    destino_estado=self._estado(i),
                    destino_cidade=self._cidade(i),
                    data_evento_inicio=_data(i),
                    data_evento_fim=_data(i) + timedelta(days=3),
                    coordenador_adm=self._servidor(i),
                    coordenador_op=self._servidor(i + 1),
                )
                for i in range(self.volume)
            ]
        )
        # `PlanoTrabalho.destino_display` (`planos_trabalho/models.py:439`) tem um
        # ramo que lê o cache de prefetch e outro que consulta. Sem nenhum
        # `PlanoDestino` semeado, os dois ramos devolviam vazio e a régua não
        # media diferença entre eles. Dois por plano, mais um amarrado a evento,
        # porque a propriedade filtra `evento_id is None` — se o filtro sumir, o
        # texto muda e agora dá para perceber.
        PlanoDestino.objects.bulk_create(
            [
                PlanoDestino(
                    plano=plano,
                    estado=self._estado(i + d),
                    cidade=self._cidade(i + d),
                    ordem=d,
                )
                for i, plano in enumerate(planos)
                for d in range(2)
            ]
        )

    def semear_ordens_servico(self):
        from ordens_servico.models import OrdemServico

        areas = _fatiar_por_area(self.volume, self.areas)
        ordens = OrdemServico.objects.bulk_create(
            [
                OrdemServico(
                    area=areas[i],
                    numero=i + 1,
                    ano=2026,
                    evento=self.eventos[i % len(self.eventos)] if self.eventos else None,
                    data_evento_inicio=_data(i),
                    data_evento_fim=_data(i) + timedelta(days=2),
                    motivo="Motivo da ordem de serviço.",
                    motorista_equipe=self._servidor(i),
                )
                for i in range(self.volume)
            ]
        )
        OrdemServico.servidores.through.objects.bulk_create(
            [
                OrdemServico.servidores.through(
                    ordemservico_id=ordem.pk, servidor_id=self._servidor(i + s).pk
                )
                for i, ordem in enumerate(ordens)
                for s in range(3)
            ]
        )
        # Quatro destinos por OS, não um. `OrdemServico.destinos_display`
        # (`ordens_servico/models.py:183`) mostra os **três primeiros** por nome e
        # resume o resto: com um destino só, o corte `[:3]` e a ordenação nunca
        # eram exercitados, e a régua media um caminho que produção não usa.
        # Achado pela verificação adversarial do `NOVO-08`.
        OrdemServico.destinos.through.objects.bulk_create(
            [
                OrdemServico.destinos.through(
                    ordemservico_id=ordem.pk, cidade_id=self._cidade(i + d).pk
                )
                for i, ordem in enumerate(ordens)
                for d in range(4)
            ]
        )

    def semear_justificativas(self):
        from justificativas.models import Justificativa
        from justificativas.models import ModeloJustificativa

        modelos = ModeloJustificativa.objects.bulk_create(
            [ModeloJustificativa(nome=f"Modelo {i}", texto="Texto do modelo.") for i in range(5)]
        )
        # 1:1 com ofício — o volume é o mesmo pool, sem criar ofício extra.
        Justificativa.objects.bulk_create(
            [
                Justificativa(
                    evento=oficio.evento,
                    oficio=oficio,
                    modelo=modelos[i % len(modelos)],
                    texto="Justificativa de encaminhamento fora do prazo.",
                    primeira_saida_dt=_dt(i, 7),
                )
                for i, oficio in enumerate(self.oficios)
            ]
        )

    def semear_prestacoes(self):
        from prestacoes_contas.models import PrestacaoContas
        from prestacoes_contas.models import PrestacaoServidor

        prestacoes = PrestacaoContas.objects.bulk_create(
            [
                PrestacaoContas(area=oficio.area, oficio=oficio, observacoes="Observação.")
                for oficio in self.oficios
            ]
        )
        # A lista de prestações é por **servidor**, não por prestação: sem estas
        # linhas ela mediria uma tela vazia.
        PrestacaoServidor.objects.bulk_create(
            [
                PrestacaoServidor(prestacao=prestacao, servidor=self._servidor(i + s))
                for i, prestacao in enumerate(prestacoes)
                for s in range(2)
            ]
        )

    def semear_tudo(self):
        """Ordem importa: ofício depende de evento e roteiro; prestação, de ofício."""
        etapas = [
            ("base", self.semear_base),
            ("eventos", self.semear_eventos),
            ("roteiros", self.semear_roteiros),
            ("oficios", self.semear_oficios),
            ("termos", self.semear_termos),
            ("planos de trabalho", self.semear_planos),
            ("ordens de serviço", self.semear_ordens_servico),
            ("justificativas", self.semear_justificativas),
            ("prestações", self.semear_prestacoes),
        ]
        for nome, funcao in etapas:
            comeco = time.perf_counter()
            funcao()
            print(f"    {nome:22} {(time.perf_counter() - comeco) * 1000:8.0f} ms", flush=True)


# ── Medição ──────────────────────────────────────────────────────────────────


def _linhas_na_pagina(resposta):
    """Quantas linhas a página realmente renderizou.

    Existe porque contagem de consulta só se compara entre páginas igualmente
    cheias: 11 consultas com 3 linhas e 11 com 20 linhas dizem coisas opostas.
    Todas as listas medidas expõem `page_obj`; se alguma parar de expor, o valor
    vira `None` e aparece como `?` no relatório em vez de virar zero silencioso.
    """
    contexto = getattr(resposta, "context", None)
    if contexto is None:
        return None
    try:
        page_obj = contexto["page_obj"]
    except (KeyError, TypeError):
        return None
    return len(page_obj.object_list)


def medir_rota(client, nome_rota, repeticoes, *, params=None):
    url = reverse(nome_rota)
    params = params or {}

    # Uma requisição descartada antes de medir: a primeira paga compilação de
    # template e preenchimento de cache de app. Em produção esse custo é pago uma
    # vez por processo, não por requisição — medir o regime estável é o que
    # descreve o que o usuário sente na segunda tela em diante.
    resposta = client.get(url, params)
    if resposta.status_code != 200:
        raise SystemExit(f"{nome_rota} respondeu {resposta.status_code}, esperava 200")

    tempos = []
    consultas = None
    for _ in range(repeticoes):
        with CaptureQueriesContext(connection) as capturadas:
            comeco = time.perf_counter()
            resposta = client.get(url, params)
            tempos.append((time.perf_counter() - comeco) * 1000)
        consultas = len(capturadas)

    return {
        "consultas": consultas,
        "linhas": _linhas_na_pagina(resposta),
        "kb_html": round(len(resposta.content) / 1024, 1),
        "ms": round(statistics.median(tempos), 1),
        "ms_min": round(min(tempos), 1),
        "ms_max": round(max(tempos), 1),
    }


def medir_volume(volume, repeticoes):
    print(f"\n── volume {volume:,} por domínio ──".replace(",", "."), flush=True)
    print("  semeando:", flush=True)
    semeador = Semeador(volume)
    semeador.semear_tudo()

    client = Client()
    client.force_login(semeador.user)

    medidas = {}
    for nome_rota, rotulo in ROTAS:
        medidas[nome_rota] = medir_rota(client, nome_rota, repeticoes)
        medidas[nome_rota]["dominio"] = rotulo
    for chave, nome_rota, rotulo, params in CENARIOS_COM_QUERY:
        medidas[chave] = medir_rota(client, nome_rota, repeticoes, params=params)
        medidas[chave]["dominio"] = rotulo
    return medidas


# ── Tetos ────────────────────────────────────────────────────────────────────


def carregar_tetos():
    if not ARQUIVO_TETOS.exists():
        return {}
    return json.loads(ARQUIVO_TETOS.read_text(encoding="utf-8")).get("rotas", {})


def _teto_de_kb(medido):
    """Margem no byte, folga zero na consulta.

    Contagem de consulta é exata: 11 é 11, e 12 é regressão. Tamanho de HTML não —
    trocar "Nenhum registro" por "Nenhum registro encontrado" muda dezenas de bytes
    sem nada a ver com desempenho, e um teto colado no valor medido reprovaria o
    gate de desempenho por edição de texto. 5%, com piso de 2 KB para as páginas
    pequenas: absorve mexida de conteúdo e ainda pega um ícone novo por cartão ou
    um despejo de tabela inteira, que é o que o `PF-01` e o `NOVO-07` são.
    """
    return round(max(medido * 1.05, medido + 2), 1)


def gravar_tetos(medidas_por_volume, *, permitir_subir=False):
    """Regrava os tetos, **recusando subir** a menos que peçam explicitamente.

    A catraca deste projeto só desce. Sem esta guarda, o jeito mais fácil de
    apagar uma regressão de desempenho seria rodar `--atualizar-tetos` — o
    comando que existe justamente para registrar melhora. O aviso é impresso com
    o valor antigo e o novo, para quem autorizar a subida saber o que está
    autorizando.
    """
    anteriores = carregar_tetos()
    subidas = []
    rotas = {}
    for volume, medidas in medidas_por_volume.items():
        for nome_rota, medida in medidas.items():
            novo_teto = {
                "consultas": medida["consultas"],
                "kb_html": _teto_de_kb(medida["kb_html"]),
            }
            antigo_teto = anteriores.get(nome_rota, {}).get(str(volume))
            if antigo_teto:
                for chave in ("consultas", "kb_html"):
                    if novo_teto[chave] > antigo_teto[chave]:
                        subidas.append(
                            f"{nome_rota} @ {volume}: {chave} {antigo_teto[chave]} → {novo_teto[chave]}"
                        )
                        if not permitir_subir:
                            novo_teto[chave] = antigo_teto[chave]
            rotas.setdefault(nome_rota, {})[str(volume)] = novo_teto

    if subidas:
        titulo = "TETOS SUBIRAM" if permitir_subir else "TETOS QUE SUBIRIAM (mantidos no valor antigo)"
        print(f"\n=== {titulo} ===")
        for subida in subidas:
            print(f"  {subida}")
        if not permitir_subir:
            print("\n  Use --permitir-subir-teto se a subida for deliberada, e explique no PR.")
    ARQUIVO_TETOS.write_text(
        json.dumps(
            {
                "_leia": (
                    "PF-07 — teto por rota e por volume. Catraca: estes números só descem. "
                    "`consultas` é o valor medido, sem folga. `kb_html` tem 5% de margem "
                    "(piso de 2 KB) para não reprovar por edição de texto — ver `_teto_de_kb`. "
                    "Gerado por `python scripts/medir_desempenho.py --atualizar-tetos`; "
                    "quem subir um teto explica por quê no corpo do PR. "
                    "Tempo não entra aqui de propósito — ver o docstring do script."
                ),
                "rotas": dict(sorted(rotas.items())),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        onde = ARQUIVO_TETOS.relative_to(RAIZ)
    except ValueError:
        onde = ARQUIVO_TETOS  # destino fora do repositório (teste, sandbox)
    print(f"\ntetos regravados em {onde}")


def conferir_tetos(medidas_por_volume, tetos):
    violacoes = []
    for volume, medidas in medidas_por_volume.items():
        for nome_rota, medida in medidas.items():
            teto = tetos.get(nome_rota, {}).get(str(volume))
            if teto is None:
                violacoes.append(f"{nome_rota} @ {volume}: sem teto declarado")
                continue
            for chave, unidade in (("consultas", ""), ("kb_html", " KB")):
                if medida[chave] > teto[chave]:
                    violacoes.append(
                        f"{nome_rota} @ {volume}: {chave} {medida[chave]}{unidade} "
                        f"passou do teto {teto[chave]}{unidade}"
                    )
    return violacoes


# ── Relatório ────────────────────────────────────────────────────────────────


def imprimir(medidas_por_volume, tetos):
    for volume, medidas in medidas_por_volume.items():
        print(f"\n═══ volume {volume} por domínio ═══")
        print(
            f"{'rota':30} {'linhas':>7} {'consultas':>10} {'teto':>6} "
            f"{'KB html':>9} {'teto':>8} {'ms':>8}"
        )
        print(f"{'-' * 30} {'-' * 7} {'-' * 10} {'-' * 6} {'-' * 9} {'-' * 8} {'-' * 8}")
        for nome_rota, medida in medidas.items():
            teto = tetos.get(nome_rota, {}).get(str(volume), {})
            linhas = medida["linhas"] if medida["linhas"] is not None else "?"
            print(
                f"{nome_rota:30} {linhas:>7} {medida['consultas']:>10} "
                f"{teto.get('consultas', '—'):>6} {medida['kb_html']:>9} "
                f"{teto.get('kb_html', '—'):>8} {medida['ms']:>8}"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--volumes",
        default="200,20000",
        help="volumes por domínio, separados por vírgula (padrão: 200,20000)",
    )
    parser.add_argument("--repeticoes", type=int, default=5, help="medições por rota (padrão: 5)")
    parser.add_argument("--json", type=Path, help="salva o relatório completo neste arquivo")
    parser.add_argument(
        "--atualizar-tetos",
        action="store_true",
        help="regrava scripts/tetos_desempenho.json com o que foi medido (não use no CI)",
    )
    parser.add_argument(
        "--permitir-subir-teto",
        action="store_true",
        help="autoriza --atualizar-tetos a subir um teto; sem isto, subida é recusada",
    )
    args = parser.parse_args()

    volumes = [int(v) for v in args.volumes.split(",") if v.strip()]

    exigir_postgres()

    setup_test_environment()
    medidas_por_volume = {}
    try:
        for volume in volumes:
            # Um banco por volume, criado e destruído: `flush` entre volumes
            # deixaria sequência de id e estatística de planejador do volume
            # anterior, e o plano de consulta do Postgres depende das duas.
            nome_antigo = connection.creation.create_test_db(verbosity=0, autoclobber=True)
            try:
                medidas_por_volume[volume] = medir_volume(volume, args.repeticoes)
            finally:
                connection.close()
                connection.creation.destroy_test_db(nome_antigo, verbosity=0)
    finally:
        teardown_test_environment()

    tetos = carregar_tetos()
    imprimir(medidas_por_volume, tetos)

    if args.json:
        args.json.write_text(
            json.dumps(medidas_por_volume, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nrelatório em {args.json}")

    if args.atualizar_tetos:
        gravar_tetos(medidas_por_volume, permitir_subir=args.permitir_subir_teto)
        return 0

    violacoes = conferir_tetos(medidas_por_volume, tetos)
    if violacoes:
        print("\n=== TETO ESTOURADO ===")
        for violacao in violacoes:
            print(f"  {violacao}")
            print(f"::error title=Regressão de desempenho::{violacao}")
        return 1

    print("\nOK: nenhuma rota passou do teto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
