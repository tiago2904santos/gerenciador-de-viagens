from django.urls import path

from . import views


app_name = "oficios"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("modelos-motivo/", views.modelos_motivo_index, name="modelos_motivo_index"),
    path("modelos-motivo/novo/", views.modelo_motivo_novo, name="modelo_motivo_novo"),
    path("modelos-motivo/<int:pk>/editar/", views.modelo_motivo_editar, name="modelo_motivo_editar"),
    path(
        "modelos-motivo/<int:pk>/padrao/",
        views.modelo_motivo_definir_padrao,
        name="modelo_motivo_definir_padrao",
    ),
    path("modelos-motivo/<int:pk>/excluir/", views.modelo_motivo_excluir, name="modelo_motivo_excluir"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/dados-viajantes/", views.dados_viajantes, name="dados_viajantes"),
    path("<int:pk>/dados-viajantes/autosave/", views.dados_viajantes_autosave, name="dados_viajantes_autosave"),
    path("<int:pk>/transporte/", views.transporte, name="transporte"),
    path("<int:pk>/transporte/autosave/", views.transporte_autosave, name="transporte_autosave"),
    path("<int:pk>/roteiro/", views.wizard_roteiro, name="wizard_roteiro"),
    path("<int:pk>/justificativa/", views.wizard_justificativa, name="wizard_justificativa"),
    path("<int:pk>/justificativa/autosave/", views.justificativa_autosave, name="justificativa_autosave"),
    path("<int:pk>/resumo/", views.wizard_resumo, name="wizard_resumo"),
    path("<int:pk>/api/viatura-por-placa/", views.api_viatura_por_placa, name="api_viatura_por_placa"),
    path("<int:pk>/documentos/", views.wizard_documentos, name="wizard_documentos"),
    path("<int:pk>/documentos/oficio-pdf-inline/", views.oficio_pdf_inline, name="oficio_pdf_inline"),
    path(
        "<int:pk>/documentos/justificativa-pdf-inline/",
        views.justificativa_pdf_inline,
        name="justificativa_pdf_inline",
    ),
    path(
        "<int:pk>/documentos/ordem-servico-pdf-inline/",
        views.ordem_servico_pdf_inline,
        name="ordem_servico_pdf_inline",
    ),
    path(
        "<int:pk>/documentos/justificativa/<str:formato>/",
        views.baixar_justificativa_documento,
        name="baixar_justificativa_documento",
    ),
    path(
        "<int:pk>/documentos/ordem-servico/<str:formato>/",
        views.baixar_ordem_servico_documento,
        name="baixar_ordem_servico_documento",
    ),
    path("<int:pk>/documentos/<str:formato>/", views.baixar_documento, name="baixar_documento"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
