from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.usuario_create, name="usuario_create"),
    path("<int:pk>/", views.usuario_update, name="usuario_update"),
    path("<int:pk>/excluir/", views.usuario_delete, name="usuario_delete"),
    path("vinculos/novo/", views.vinculo_create, name="vinculo_create"),
    path("vinculos/<int:pk>/excluir/", views.vinculo_delete, name="vinculo_delete"),
    path("areas/", views.areas_index, name="areas_index"),
    path("areas/nova/", views.area_create, name="area_create"),
    path("areas/<int:pk>/", views.area_update, name="area_update"),
    path("areas/<int:pk>/excluir/", views.area_delete, name="area_delete"),
    path("areas/<int:pk>/vinculos/", views.vinculo_create_na_area, name="vinculo_create_na_area"),
]
