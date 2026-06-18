from django.urls import path

from . import views


app_name = "prestacoes"

urlpatterns = [
    path("eventos/<int:evento_pk>/relatorio/novo/", views.criar_relatorio_evento, name="criar_relatorio_evento"),
    path("relatorios/<int:pk>/editar/", views.editar_relatorio, name="editar_relatorio"),
    path("eventos/<int:evento_pk>/diario/novo/", views.criar_diario_evento, name="criar_diario_evento"),
    path("diarios/<int:pk>/editar/", views.editar_diario, name="editar_diario"),
    path("diarios/<int:diario_pk>/registros/novo/", views.adicionar_registro_diario, name="adicionar_registro_diario"),
    path("eventos/<int:evento_pk>/prestacao/", views.criar_ou_editar_prestacao, name="prestacao_evento"),
    path("prestacoes/<int:pk>/editar/", views.editar_prestacao, name="editar_prestacao"),
]
