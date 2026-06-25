from django.urls import path

from . import views


app_name = "justificativas"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/excluir/", views.justificativa_excluir, name="justificativa_excluir"),
    path("modelos/", views.modelos_index, name="modelos_index"),
    path("modelos/novo/", views.modelo_novo, name="modelo_novo"),
    path("modelos/<int:pk>/editar/", views.modelo_editar, name="modelo_editar"),
    path("modelos/<int:pk>/padrao/", views.modelo_definir_padrao, name="modelo_definir_padrao"),
    path("modelos/<int:pk>/excluir/", views.modelo_excluir, name="modelo_excluir"),
    path("novo/", views.legacy_modelos_redirect, name="legacy_modelo_novo"),
    path("<int:pk>/editar/", views.legacy_modelos_redirect, name="legacy_modelo_editar"),
    path("<int:pk>/padrao/", views.legacy_modelos_redirect, name="legacy_modelo_definir_padrao"),
    path("<int:pk>/excluir/", views.legacy_modelos_redirect, name="legacy_modelo_excluir"),
]
