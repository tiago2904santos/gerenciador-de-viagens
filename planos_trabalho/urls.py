from django.urls import path

from . import views


app_name = "planos_trabalho"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("programas/", views.programas_index, name="programas_index"),
    path("programas/novo/", views.programas_index, name="programa_create"),
    path("programas/<int:pk>/editar/", views.programa_editar, name="programa_update"),
    path("programas/<int:pk>/excluir/", views.programa_excluir, name="programa_delete"),
    path("horarios/", views.horarios_index, name="horarios_index"),
    path("horarios/novo/", views.horarios_index, name="horario_create"),
    path("horarios/<int:pk>/editar/", views.horario_editar, name="horario_update"),
    path("horarios/<int:pk>/excluir/", views.horario_excluir, name="horario_delete"),
    path("atividades/", views.atividades_index, name="atividades_index"),
    path("atividades/<int:pk>/editar/", views.atividade_editar, name="atividade_update"),
    path("atividades/<int:pk>/excluir/", views.atividade_excluir, name="atividade_delete"),
    path("presets/", views.presets_index, name="presets_index"),
    path("presets/<int:pk>/editar/", views.preset_editar, name="preset_update"),
    path("presets/<int:pk>/padrao/", views.preset_definir_padrao, name="preset_definir_padrao"),
    path("presets/<int:pk>/excluir/", views.preset_excluir, name="preset_delete"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/menus/", views.card_menus, name="card_menus"),
    path("<int:pk>/identificacao/", views.wizard_identificacao, name="wizard_identificacao"),
    path("<int:pk>/identificacao/autosave/", views.identificacao_autosave, name="identificacao_autosave"),
    path("<int:pk>/efetivo-diarias/", views.wizard_efetivo_diarias, name="wizard_efetivo_diarias"),
    path("<int:pk>/efetivo-diarias/autosave/", views.efetivo_diarias_autosave, name="efetivo_diarias_autosave"),
    path("<int:pk>/efetivo-diarias/calcular/", views.api_calcular_diarias, name="api_calcular_diarias"),
    path("<int:pk>/eventos/adicionar/", views.evento_adicionar, name="evento_adicionar"),
    path("<int:pk>/eventos/<int:evento_pk>/editar/", views.evento_editar, name="evento_update"),
    path("<int:pk>/eventos/<int:evento_pk>/remover/", views.evento_remover, name="evento_remover"),
    path("<int:pk>/atividades/", views.wizard_atividades, name="wizard_atividades"),
    path("<int:pk>/atividades/autosave/", views.atividades_autosave, name="atividades_autosave"),
    path("<int:pk>/documentos/", views.wizard_documentos, name="wizard_documentos"),
    path("<int:pk>/documentos/pdf-inline/", views.pdf_inline, name="pdf_inline"),
    path("<int:pk>/documentos/<str:formato>/", views.baixar_documento, name="baixar_documento"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
