from django.urls import path

from . import views


app_name = "justificativas"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/oficios/", views.api_buscar_oficios, name="api_buscar_oficios"),
    path("<int:pk>/excluir/", views.justificativa_excluir, name="justificativa_delete"),
    path("modelos/", views.modelos_index, name="modelos_index"),
    path("modelos/novo/", views.modelos_index, name="modelo_create"),
    path("modelos/<int:pk>/editar/", views.modelo_editar, name="modelo_update"),
    path("modelos/<int:pk>/padrao/", views.modelo_definir_padrao, name="modelo_definir_padrao"),
    path("modelos/<int:pk>/excluir/", views.modelo_excluir, name="modelo_delete"),
    path("novo/", views.legacy_modelos_redirect, name="legacy_modelo_create"),
    path("<int:pk>/editar/", views.legacy_modelos_redirect, name="legacy_modelo_update"),
    path("<int:pk>/padrao/", views.legacy_modelos_redirect, name="legacy_modelo_definir_padrao"),
    path("<int:pk>/excluir/", views.legacy_modelos_redirect, name="legacy_modelo_delete"),
]
