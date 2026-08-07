from django.urls import path

from . import views
from .card_menu_views import card_menus


app_name = "ordens_servico"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/oficios/", views.api_buscar_oficios, name="api_buscar_oficios"),
    path("nova/", views.nova, name="nova"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/menus/", card_menus, name="card_menus"),
    path("<int:pk>/baixar/", views.baixar_docx, name="baixar_docx"),
    path("<int:pk>/pdf/", views.pdf_inline, name="pdf_inline"),
    path("<int:pk>/baixar-pdf/", views.baixar_pdf, name="baixar_pdf"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
