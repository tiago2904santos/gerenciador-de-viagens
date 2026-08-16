"""Dados que a seção de destinos precisa para funcionar sozinha.

O componente `cotton/v2/destinations.html` não é aparência: ele adiciona linha,
remove, reordena por arraste e cascateia estado → cidade. Nada disso acontece
sem a lista de estados e sem a rota que devolve as cidades de um estado.

Enquanto esses dois valores vinham do contexto, usar destinos numa tela custava
duas linhas na view — e esquecer uma delas não dá erro: a seção renderiza, o
campo de estado abre vazio ou a cidade nunca habilita. É o modo de falha que
este refactor passa o tempo caçando, então o componente passou a buscá-los.

O preço é uma consulta por tela que tenha destinos. É uma tabela de 27 linhas
com `ordering` no Meta e sem join; a alternativa — um context processor —
cobraria o mesmo de toda página do sistema, inclusive as que não têm destino
nenhum.
"""

from __future__ import annotations

from django import template
from django.urls import reverse

register = template.Library()


def _memo(chave, calcular):
    """Guarda o resultado no `request` da vez — uma consulta por TELA, não por linha.

    Uma tela com quatro destinos chama a tag cinco vezes (as linhas mais o
    molde), e sem isto cada chamada refazia a lista de estados e a leitura da
    configuração. O orçamento de queries do formulário de termo pegou
    exatamente isso.

    O cache morre com a requisição de propósito: guardá-lo no módulo faria uma
    mudança em Configurações só aparecer depois de reiniciar o processo.
    """
    from core.middleware import get_current_request

    request = get_current_request()
    if request is None:
        return calcular()
    cache = getattr(request, "_destinos_memo", None)
    if cache is None:
        cache = {}
        request._destinos_memo = cache
    if chave not in cache:
        cache[chave] = calcular()
    return cache[chave]


def _uf_da_sede():
    """A UF da sede, como pk de `Estado` — ou `""` se não houver.

    Vem de `ConfiguracaoSistema.uf`, que é o campo preenchido pela busca de CEP
    na tela de Configurações. Uso o campo já gravado, e não
    `resolver_sede_ids_desde_configuracao()`: aquele resolvedor consulta o
    ViaCEP quando o texto não basta, e uma chamada de rede DENTRO da renderização
    de um campo é lentidão que aparece em toda tela com destino — e vira erro de
    página quando o serviço externo cai.

    Sem UF cadastrada, nada é pré-selecionado: chutar um estado é pior do que
    deixar em branco, porque o errado passa despercebido.
    """
    from cadastros.models import Estado
    from cadastros.selectors import get_configuracao_sistema

    try:
        sigla = (get_configuracao_sistema().uf or "").strip().upper()
    except Exception:
        return ""
    if not sigla:
        return ""
    estado = Estado.objects.filter(sigla=sigla).only("pk").first()
    return str(estado.pk) if estado else ""


@register.inclusion_tag("includes/destinos/opcoes_de_estado.html")
def destinos_opcoes_estado(estados=None, selecionado=None):
    """As `<option>` do picker de estado, já em ordem alfabética.

    É tag de inclusão, e não uma tag que devolve a lista, por causa do contrato
    dos componentes: `{% ... as nome %}` cria uma variável local que o
    `test_cotton_component_contracts` lê como entrada NÃO declarada do
    componente. Declará-la calaria o teste ao preço de anunciar como API pública
    uma variável que ninguém deve passar.

    Renderizando aqui, o componente não precisa de variável nenhuma.

    `estados` existe para quem tiver motivo para contrariar a busca — uma tela
    que filtre estados. Vazio, busca todos.

    `selecionado` é o estado já escolhido, quando a linha vem preenchida. Vazio,
    a linha nasce na UF da sede: a viagem quase sempre começa e passa pelo estado
    do próprio órgão, e deixar o campo em branco obriga a escolher de novo o que
    já está cadastrado.
    """
    if estados is None or estados == "":
        from cadastros.models import Estado

        estados = _memo("estados", lambda: list(Estado.objects.order_by("nome")))
    if selecionado in (None, ""):
        selecionado = _memo("uf_da_sede", _uf_da_sede)
    return {"estados": estados, "selecionado": str(selecionado or "")}


@register.simple_tag
def destinos_url_cidades() -> str:
    """Rota de cidades por estado, com `0` no lugar do id.

    O `location-rows.js` troca o `0` pelo estado escolhido. O formato do
    marcador é contrato dele — ver `loadCities`, que faz
    ``template.replace("/0/", ...)``.
    """
    return reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0})
