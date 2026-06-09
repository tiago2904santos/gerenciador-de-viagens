from django.urls import path

from . import views


app_name = "termos"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/preview/", views.preview_cadastro, name="preview_cadastro"),
    path("<int:pk>/pdf-inline/", views.termo_cadastro_pdf_inline, name="termo_cadastro_pdf_inline"),
    path("<int:pk>/pdf/", views.baixar_termo_cadastro_pdf, name="baixar_termo_cadastro_pdf"),
    path("<int:pk>/docx/", views.baixar_termo_cadastro_docx, name="baixar_termo_cadastro_docx"),
    path("oficio/<int:pk>/preview/", views.preview_termo_oficio, name="preview_termo_oficio"),
    path(
        "oficio/<int:pk>/servidor/<int:servidor_pk>/pdf-inline/",
        views.termo_servidor_pdf_inline,
        name="termo_servidor_pdf_inline",
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
