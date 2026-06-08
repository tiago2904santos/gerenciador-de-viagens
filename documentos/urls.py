from django.urls import path

from . import views


app_name = "documentos"

urlpatterns = [
    path("", views.index, name="index"),
    path("artefatos/<uuid:pk>/visualizar/", views.artefato_pdf_visualizar, name="artefato_pdf_visualizar"),
    path("artefatos/<uuid:pk>/conteudo/", views.artefato_pdf_conteudo, name="artefato_pdf_conteudo"),
    path("artefatos/conteudo-publico/", views.artefato_pdf_conteudo_publico, name="artefato_pdf_conteudo_publico"),
]
