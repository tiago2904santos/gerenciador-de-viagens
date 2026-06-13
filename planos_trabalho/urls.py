from django.urls import path

from . import views


app_name = "planos_trabalho"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("programas/", views.programas_index, name="programas_index"),
    path("programas/novo/", views.programa_novo, name="programa_novo"),
    path("programas/<int:pk>/editar/", views.programa_editar, name="programa_editar"),
    path("programas/<int:pk>/excluir/", views.programa_excluir, name="programa_excluir"),
    path("horarios/", views.horarios_index, name="horarios_index"),
    path("horarios/novo/", views.horario_novo, name="horario_novo"),
    path("horarios/<int:pk>/editar/", views.horario_editar, name="horario_editar"),
    path("horarios/<int:pk>/excluir/", views.horario_excluir, name="horario_excluir"),
    path("atividades/", views.atividades_index, name="atividades_index"),
    path("atividades/novo/", views.atividade_novo, name="atividade_novo"),
    path("atividades/<int:pk>/editar/", views.atividade_editar, name="atividade_editar"),
    path("atividades/<int:pk>/excluir/", views.atividade_excluir, name="atividade_excluir"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/identificacao/", views.wizard_identificacao, name="wizard_identificacao"),
    path("<int:pk>/identificacao/autosave/", views.identificacao_autosave, name="identificacao_autosave"),
    path("<int:pk>/efetivo-diarias/", views.wizard_efetivo_diarias, name="wizard_efetivo_diarias"),
    path("<int:pk>/efetivo-diarias/calcular/", views.api_calcular_diarias, name="api_calcular_diarias"),
    path("<int:pk>/atividades/", views.wizard_atividades, name="wizard_atividades"),
    path("<int:pk>/documentos/", views.wizard_documentos, name="wizard_documentos"),
    path("<int:pk>/documentos/pdf-inline/", views.pdf_inline, name="pdf_inline"),
    path("<int:pk>/documentos/<str:formato>/", views.baixar_documento, name="baixar_documento"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
