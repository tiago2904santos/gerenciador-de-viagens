from django.urls import path

from . import views
from . import assinatura_views


app_name = "prestacoes_contas"

urlpatterns = [
    path("", views.index, name="index"),
    # Ações por servidor (canônicas)
    path(
        "servidor-prestacao/<int:ps_pk>/arquivar/",
        views.prestacao_servidor_arquivar,
        name="prestacao_servidor_arquivar",
    ),
    path(
        "servidor-prestacao/<int:ps_pk>/finalizar/",
        views.prestacao_servidor_finalizar,
        name="prestacao_servidor_finalizar",
    ),
    path(
        "servidor-prestacao/<int:ps_pk>/documentos/",
        views.documentos_servidor,
        name="documentos_servidor",
    ),
    path("servidor-prestacao/<int:ps_pk>/rt/", views.rt_servidor, name="rt_servidor"),
    path(
        "servidor-prestacao/<int:ps_pk>/diario/",
        views.diario_servidor,
        name="diario_servidor",
    ),
    path(
        "servidor-prestacao/<int:ps_pk>/consolidado/",
        views.consolidado_servidor,
        name="consolidado_servidor",
    ),
    # Compatibilidade: URLs por ofício redirecionam para o 1º servidor
    path("prestacao/<int:pc_pk>/arquivar/", views.prestacao_arquivar, name="prestacao_arquivar"),
    path("prestacao/<int:pc_pk>/finalizar/", views.prestacao_finalizar, name="prestacao_finalizar"),
    path("prestacao/<int:pc_pk>/documentos/", views.documentos, name="documentos"),
    path("prestacao/<int:pc_pk>/despacho/autosave/", views.prestacao_arquivo_autosave, name="prestacao_arquivo_autosave"),
    path(
        "prestacao/<int:pc_pk>/despacho-assinado/anexar/",
        views.prestacao_despacho_assinado_anexar,
        name="prestacao_despacho_assinado_anexar",
    ),
    path(
        "servidor-prestacao/<int:ps_pk>/assinado/<str:tipo>/anexar/",
        views.prestacao_servidor_assinado_anexar,
        name="prestacao_servidor_assinado_anexar",
    ),
    path("prestacao/<int:pc_pk>/anexo/<int:anexo_pk>/excluir/", views.prestacao_documento_excluir, name="prestacao_documento_excluir"),
    path("servidor-prestacao/<int:ps_pk>/solicitacao/autosave/", views.prestacao_servidor_solicitacao_autosave, name="prestacao_servidor_solicitacao_autosave"),
    path("servidor-prestacao/<int:ps_pk>/comprovante/autosave/", views.prestacao_servidor_arquivo_autosave, name="prestacao_servidor_arquivo_autosave"),
    path("prestacao/<int:pc_pk>/rt/", views.rt_criar, name="rt_criar"),
    path("rt/<int:pk>/autosave/", views.rt_autosave, name="rt_autosave"),
    path(
        "servidor-prestacao/<int:ps_pk>/rt/autosave/",
        views.rt_servidor_autosave,
        name="rt_servidor_autosave",
    ),
    path("rt/servidor/<int:ps_pk>/download/", views.rt_download_servidor, name="rt_download_servidor"),
    path("rt/servidor/<int:ps_pk>/download/<str:formato>/", views.rt_download_servidor, name="rt_download_servidor_formato"),
    path("prestacao/<int:pc_pk>/diario/", views.diario_criar, name="diario_criar"),
    path("prestacao/<int:pc_pk>/diario/editar-roteiro/", views.diario_editar_roteiro, name="diario_editar_roteiro"),
    path(
        "servidor-prestacao/<int:ps_pk>/diario/editar-roteiro/",
        views.diario_servidor_editar_roteiro,
        name="diario_servidor_editar_roteiro",
    ),
    path("prestacao/<int:pc_pk>/diario/motorista/", views.diario_motorista, name="diario_motorista"),
    path(
        "servidor-prestacao/<int:ps_pk>/diario/motorista/",
        views.diario_servidor_motorista,
        name="diario_servidor_motorista",
    ),
    path("diario/<int:pk>/autosave/", views.diario_autosave, name="diario_autosave"),
    path(
        "servidor-prestacao/<int:ps_pk>/diario/autosave/",
        views.diario_servidor_autosave,
        name="diario_servidor_autosave",
    ),
    path("diario/<int:pk>/download/", views.diario_download, name="diario_download"),
    path("diario/<int:pk>/download/<str:formato>/", views.diario_download, name="diario_download_formato"),
    path("prestacao/<int:pc_pk>/consolidado/", views.consolidado, name="consolidado"),
    path("servidor-prestacao/<int:ps_pk>/consolidado/download/", views.consolidado_download, name="consolidado_download"),
    # Assinatura eletrônica — geração de link (admin)
    path("servidor-prestacao/<int:ps_pk>/assinatura-rt/gerar/", views.assinatura_rt_gerar, name="assinatura_rt_gerar"),
    path("servidor-prestacao/<int:ps_pk>/assinatura-rt/cancelar/", views.assinatura_rt_cancelar, name="assinatura_rt_cancelar"),
    path("prestacao/<int:pc_pk>/assinatura-db/gerar/", views.assinatura_db_gerar, name="assinatura_db_gerar"),
    path("prestacao/<int:pc_pk>/assinatura-db/cancelar/", views.assinatura_db_cancelar, name="assinatura_db_cancelar"),
    # Assinatura eletrônica — fluxo público (sem login)
    path("assinar/<str:token>/", assinatura_views.publico_landing, name="assinatura_landing"),
    path("assinar/<str:token>/concluido/", assinatura_views.publico_concluido, name="assinatura_concluido"),
    path("assinar/<str:token>/<str:tipo>/identidade/", assinatura_views.publico_identidade, name="assinatura_identidade"),
    path("assinar/<str:token>/<str:tipo>/assinar/", assinatura_views.publico_assinar, name="assinatura_assinar"),
    path("assinar/<str:token>/<str:tipo>/pdf/", assinatura_views.publico_pdf_origem, name="assinatura_pdf_origem"),
    # Modelos de texto reutilizáveis
    path("modelos-texto/", views.modelos_index, name="modelos_index"),
    path("modelos-texto/novo/", views.modelo_novo, name="modelo_novo"),
    path("modelos-texto/<int:pk>/editar/", views.modelo_editar, name="modelo_editar"),
    path("modelos-texto/<int:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
]
