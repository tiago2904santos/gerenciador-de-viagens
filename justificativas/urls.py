from django.urls import path

from . import views


app_name = "justificativas"

urlpatterns = [
    path("", views.modelos_index, name="index"),
    path("novo/", views.modelo_novo, name="modelo_novo"),
    path("<int:pk>/editar/", views.modelo_editar, name="modelo_editar"),
    path("<int:pk>/padrao/", views.modelo_definir_padrao, name="modelo_definir_padrao"),
    path("<int:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
]
