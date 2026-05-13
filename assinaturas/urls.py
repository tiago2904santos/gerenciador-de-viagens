from django.urls import path

from . import views


app_name = "assinaturas"

urlpatterns = [
    path("", views.index, name="index"),
    path("gestao/", views.assinatura_gestao, name="assinatura-gestao"),
    path(
        "artefatos/<uuid:artefato_id>/assinar/",
        views.assinar_artefato,
        name="assinatura-assinar-artefato",
    ),
    path(
        "artefatos/<uuid:artefato_id>/gerar-link/",
        views.gerar_link_assinatura,
        name="gerar-link-assinatura",
    ),
    path(
        "pedidos/<str:token>/assinar/",
        views.assinar_pedido,
        name="assinar-pedido",
    ),
    path("pedidos/<str:token>/revogar/", views.revogar_pedido, name="revogar-pedido"),
    path("assinar/<str:token>/", views.assinatura_token, name="assinatura-token"),
    path("assinar/<str:token>/confirmar/", views.assinatura_token_confirmar, name="assinatura-token-confirmar"),
    path("assinar/<str:token>/recusar/", views.assinatura_token_recusar, name="assinatura-token-recusar"),
    path("assinar/<str:token>/pdf-original/", views.assinatura_token_pdf_original, name="assinatura-token-pdf-original"),
    path("sucesso/<str:token>/", views.assinatura_sucesso, name="assinatura-sucesso"),
    path(
        "artefatos/<uuid:artefato_id>/pdf-original/",
        views.assinatura_artefato_pdf_original,
        name="assinatura-artefato-pdf-original",
    ),
    path("verificar/<str:codigo>/", views.assinatura_verificar_codigo, name="assinatura-verificar-codigo"),
    path("<uuid:assinatura_id>/pdf-original/", views.assinatura_pdf_original, name="assinatura-pdf-original"),
    path("<uuid:assinatura_id>/pdf-assinado/", views.assinatura_pdf_assinado, name="assinatura-pdf-assinado"),
    path("api/documentos/<uuid:pk>/verificar/", views.api_verificar_documento, name="api_verificar_documento"),
    path("api/documentos/<uuid:pk>/assinar/", views.api_assinar_documento, name="api_assinar_documento"),
]
