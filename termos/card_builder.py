"""Um lugar só para montar o card de termo da lista (`PF-04`).

`apresentar_termo_card` recebe uma dúzia de argumentos — URLs de PDF e DOCX do
termo, do genérico, da viatura, construtores de URL por servidor, e o mapa de
artefatos assinados. Antes do `PF-04` isso vivia inline em `termos/views.py`, o
que estava bem enquanto havia um chamador só.

Com o endpoint de menus passou a haver dois. Repetir a dúzia de argumentos lá
faria o menu servido divergir do menu que a lista teria embutido — sem levantar
erro, e sem que `test_paridade_de_acoes_com_o_caminho_embutido` conseguisse
comparar, porque ele compara justamente contra este caminho.

Então a montagem mora aqui e os dois chamam.
"""

from __future__ import annotations

from django.urls import reverse

from documentos.selectors import mapa_artefatos_pdf_termo_cadastro_em_lote

from .presenters import apresentar_termo_card
from .services import termo_cadastro_assinado_info


def _servidor_url(termo_pk):
    def build(servidor_pk, formato):
        return reverse(
            "termos:baixar_termo_cadastro_servidor",
            args=[termo_pk, servidor_pk, formato],
        )

    return build


def _servidor_view_url(termo_pk):
    def build(servidor_pk):
        return reverse(
            "termos:termo_cadastro_servidor_pdf_inline",
            args=[termo_pk, servidor_pk],
        )

    return build


def montar_card_de_termo(termo, *, artefatos=None, menus_sob_demanda=True):
    """Card de um termo, do jeito que a lista monta.

    `artefatos` é o mapa que o `NOVO-08` introduziu para a lista não consultar
    artefato por linha. Quando não vem — caso do endpoint, que trata de um termo
    só —, é resolvido aqui para este termo apenas.
    """
    if artefatos is None:
        artefatos = mapa_artefatos_pdf_termo_cadastro_em_lote([termo.pk]).get(termo.pk, {})

    return apresentar_termo_card(
        termo,
        menus_sob_demanda=menus_sob_demanda,
        edit_url=reverse("termos:editar", args=[termo.pk]),
        delete_url=reverse("termos:excluir", args=[termo.pk]),
        delete_modal=True,
        pdf_url=reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
        docx_url=reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
        generico_pdf_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "pdf"]),
        generico_docx_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "docx"]),
        servidor_url_builder=_servidor_url(termo.pk),
        servidor_view_url_builder=_servidor_view_url(termo.pk),
        viatura_view_url=reverse("termos:termo_cadastro_viatura_pdf_inline", args=[termo.pk]),
        viatura_pdf_url=reverse("termos:baixar_termo_cadastro_viatura", args=[termo.pk, "pdf"]),
        viatura_docx_url=reverse("termos:baixar_termo_cadastro_viatura", args=[termo.pk, "docx"]),
        **termo_cadastro_assinado_info(termo, None, artefatos),
    )
