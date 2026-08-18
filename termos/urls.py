from django.urls import path

from . import views


app_name = "termos"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/oficios/", views.api_buscar_oficios, name="api_buscar_oficios"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/downloads/", views.termo_cadastro_downloads, name="termo_cadastro_downloads"),
    path("<int:pk>/pdf-inline/", views.termo_cadastro_pdf_inline, name="termo_cadastro_pdf_inline"),
    path(
        "<int:pk>/pdf-inline/generico/",
        views.termo_cadastro_generico_pdf_inline,
        name="termo_cadastro_generico_pdf_inline",
    ),
    path(
        "<int:pk>/servidor/<int:servidor_pk>/pdf-inline/",
        views.termo_cadastro_servidor_pdf_inline,
        name="termo_cadastro_servidor_pdf_inline",
    ),
    path("<int:pk>/pdf/", views.baixar_termo_cadastro_pdf, name="baixar_termo_cadastro_pdf"),
    path("<int:pk>/docx/", views.baixar_termo_cadastro_docx, name="baixar_termo_cadastro_docx"),
    path(
        "<int:pk>/generico/assinado/anexar/",
        views.termo_cadastro_generico_assinado_anexar,
        name="termo_cadastro_generico_assinado_anexar",
    ),
    path(
        "<int:pk>/servidor/<int:servidor_pk>/assinado/anexar/",
        views.termo_cadastro_servidor_assinado_anexar,
        name="termo_cadastro_servidor_assinado_anexar",
    ),
    # Downloads por modo. Declarados apos as rotas literais acima
    # ("pdf-inline/", "assinado/anexar/") para que <str:formato> nao as capture.
    path(
        "<int:pk>/viatura/pdf-inline/",
        views.termo_cadastro_viatura_pdf_inline,
        name="termo_cadastro_viatura_pdf_inline",
    ),
    path(
        "<int:pk>/viatura/<str:formato>/",
        views.baixar_termo_cadastro_viatura,
        name="baixar_termo_cadastro_viatura",
    ),
    path(
        "<int:pk>/generico/<str:formato>/",
        views.baixar_termo_cadastro_generico,
        name="baixar_termo_cadastro_generico",
    ),
    path(
        "<int:pk>/servidor/<int:servidor_pk>/<str:formato>/",
        views.baixar_termo_cadastro_servidor,
        name="baixar_termo_cadastro_servidor",
    ),
    path("oficio/<int:pk>/preview/", views.preview_termo_oficio, name="preview_termo_oficio"),
    path(
        "oficio/<int:pk>/servidor/<int:servidor_pk>/pdf-inline/",
        views.termo_servidor_pdf_inline,
        name="termo_servidor_pdf_inline",
    ),
    path(
        "oficio/<int:pk>/servidor/<int:servidor_pk>/assinado/anexar/",
        views.termo_oficio_assinado_anexar,
        name="termo_oficio_assinado_anexar",
    ),
    path(
        "oficio/<int:pk>/servidor/<int:servidor_pk>/<str:formato>/",
        views.baixar_termo_servidor,
        name="baixar_termo_servidor",
    ),
    path(
        "oficio/<int:pk>/todos/pdf/",
        views.baixar_termos_todos_pdf,
        name="baixar_termos_todos_pdf",
    ),
    path(
        "oficio/<int:pk>/lote/<str:formato>/",
        views.baixar_termo_lote_zip,
        name="baixar_termo_lote_zip",
    ),
]
