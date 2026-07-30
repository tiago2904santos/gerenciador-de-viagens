from django.urls import path

from . import views


app_name = "documentos"

urlpatterns = [
    path("", views.index, name="index"),
    path("geracoes/<uuid:pk>/status/", views.geracao_status, name="geracao_status"),
    path("geracoes/<uuid:pk>/resultado/", views.geracao_resultado, name="geracao_resultado"),
    path("artefatos/<uuid:pk>/visualizar/", views.artefato_pdf_visualizar, name="artefato_pdf_visualizar"),
    path("artefatos/<uuid:pk>/conteudo/", views.artefato_pdf_conteudo, name="artefato_pdf_conteudo"),
    path("artefatos/conteudo-publico/", views.artefato_pdf_conteudo_publico, name="artefato_pdf_conteudo_publico"),
    path(
        "artefatos/<uuid:pk>/assinado/anexar/",
        views.artefato_assinado_anexar,
        name="artefato_assinado_anexar",
    ),
    path(
        "artefatos/<uuid:pk>/assinado/remover/",
        views.artefato_assinado_remover,
        name="artefato_assinado_remover",
    ),
]
