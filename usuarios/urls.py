from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.usuario_create, name="usuario_create"),
    path("vinculos/novo/", views.vinculo_create, name="vinculo_create"),
    path("areas/", views.areas_index, name="areas_index"),
    path("areas/nova/", views.area_create, name="area_create"),
]
