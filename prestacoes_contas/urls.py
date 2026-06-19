from django.urls import path

from . import views


app_name = "prestacoes_contas"

urlpatterns = [
    path("", views.index, name="index"),
    path("prestacao/<int:pc_pk>/rt/", views.rt_criar, name="rt_criar"),
    path("rt/<int:pk>/download/", views.rt_download, name="rt_download"),
    path("rt/<int:pk>/download/<str:formato>/", views.rt_download, name="rt_download_formato"),
    # Modelos de texto reutilizáveis
    path("modelos-texto/", views.modelos_index, name="modelos_index"),
    path("modelos-texto/novo/", views.modelo_novo, name="modelo_novo"),
    path("modelos-texto/<int:pk>/editar/", views.modelo_editar, name="modelo_editar"),
    path("modelos-texto/<int:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
]
