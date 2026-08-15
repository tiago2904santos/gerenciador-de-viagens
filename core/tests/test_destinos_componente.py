"""A seção de destinos funciona sozinha, e continua funcionando.

`<c-v2.destinations />` é usada sem argumento nenhum: sem contexto na view, sem
script de página. Tudo de que ela precisa — os estados, a rota de cidades, os
ganchos do motor — ela mesma emite.

O modo de falha que estes testes existem para pegar é o silencioso: trocar o
nome de um gancho `data-location-*` não gera erro em lugar nenhum. A página
renderiza bonita, o formulário parece certo, e os campos simplesmente param de
responder. Ninguém percebe em revisão de código, porque cada arquivo lido
sozinho parece correto.
"""

from __future__ import annotations

from django.template import Context, Template
from django.test import TestCase

from cadastros.models import ConfiguracaoSistema, Estado


def render(source: str, **contexto) -> str:
    """Renderiza um componente pela sintaxe de TAG do cotton.

    A sintaxe curta (`<c-v2.destinations />`) depende do loader que reescreve o
    arquivo antes de compilar, e `Template(...)` não passa por ele — o texto
    sairia literal, e o teste passaria a medir a própria string. É o que
    aconteceu na primeira versão destes testes.
    """
    return Template("{% load cotton %}" + source).render(Context(contexto))


class DestinosFuncionaSemArgumentoTests(TestCase):
    """A forma mínima é a forma que as telas usam."""

    MINIMA = "{% cotton v2.destinations only / %}"

    def test_emite_todos_os_ganchos_do_motor(self):
        """Cada um destes desliga uma capacidade, sem erro nenhum, se sumir."""
        html = render(self.MINIMA)

        for gancho, capacidade in (
            ("data-location-rows", "o motor não encontra a seção"),
            ("data-location-managed", "a seção não se liga sozinha"),
            ("data-location-list", "linha nova não sabe onde entrar"),
            ("data-location-template", "não há molde para clonar"),
            ("data-location-row", "a linha não é reconhecida"),
            ("data-location-state", "sem cascata estado → cidade"),
            ("data-location-city", "a cidade nunca habilita"),
            ("data-location-add", "não dá para adicionar"),
            ("data-location-remove", "não dá para remover"),
            ("data-location-drag-handle", "não dá para reordenar"),
            ("data-api-cidades-url", "a cascata não tem a que URL pedir"),
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html, f"sem `{gancho}`: {capacidade}")

    def test_nasce_com_uma_linha(self):
        """Lista de destinos sem nenhuma linha não tem por onde começar.

        Conta por `data-location-index`, que é um por linha. `data-location-row`
        é atributo booleano, sai sem `=`, e o prefixo ainda casaria com
        `data-location-rows` da seção — a conta daria outra coisa.
        """
        self.assertEqual(render(self.MINIMA).count("data-location-index"), 2)  # linha + molde

    def test_o_molde_carrega_o_marcador_de_indice(self):
        """`__index__` é o que o JS troca pelo número ao clonar."""
        self.assertIn("__index__", render(self.MINIMA))

    def test_a_rota_de_cidades_tem_o_zero_que_o_js_substitui(self):
        """`loadCities` faz `template.replace("/0/", ...)` — o formato é contrato."""
        self.assertIn("/0/", render(self.MINIMA))

    def test_a_linha_tem_as_duas_metades(self):
        html = render(self.MINIMA)
        self.assertIn("destination-row__start", html)
        self.assertIn("destination-row__end", html)

    def test_os_botoes_sao_as_variantes_do_sistema(self):
        """Adicionar é `primary`, remover é `danger` — nenhum desenho próprio."""
        html = render(self.MINIMA)
        self.assertIn("button button--primary button--icon", html)
        self.assertIn("button button--danger button--icon", html)


class EstadoInicialVemDaSedeTests(TestCase):
    """A linha nasce na UF da sede, que é a que a busca de CEP gravou."""

    def setUp(self):
        self.parana = Estado.objects.create(nome="PARANÁ", sigla="PR")
        self.santa_catarina = Estado.objects.create(nome="SANTA CATARINA", sigla="SC")

    def _configurar_uf(self, sigla: str) -> None:
        config = ConfiguracaoSistema.get_singleton()
        config.uf = sigla
        config.save(update_fields=["uf"])

    def test_pre_seleciona_a_uf_cadastrada(self):
        self._configurar_uf("SC")
        html = render("{% cotton v2.destinations only / %}")

        self.assertIn(f'value="{self.santa_catarina.pk}" selected', html)
        self.assertNotIn(f'value="{self.parana.pk}" selected', html)

    def test_sem_uf_cadastrada_nada_e_pre_selecionado(self):
        """Chutar um estado é pior que deixar em branco: o errado passa batido."""
        self._configurar_uf("")
        self.assertNotIn(" selected", render("{% cotton v2.destinations only / %}"))

    def test_uf_cadastrada_que_nao_existe_como_estado_nao_quebra(self):
        self._configurar_uf("ZZ")
        self.assertNotIn(" selected", render("{% cotton v2.destinations only / %}"))

    def test_estado_explicito_vence_a_sede(self):
        """Linha preenchida mostra o que foi salvo, não o padrão."""
        self._configurar_uf("SC")
        html = render(
            '{% cotton v2.destination_row :index="0" :estado_selecionado="pk" only / %}',
            pk=str(self.parana.pk),
        )

        self.assertIn(f'value="{self.parana.pk}" selected', html)
        self.assertNotIn(f'value="{self.santa_catarina.pk}" selected', html)
