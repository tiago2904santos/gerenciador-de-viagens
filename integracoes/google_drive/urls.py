from django.urls import path

from . import views

app_name = "google_drive"

urlpatterns = [
    path("", views.index, name="index"),
    path("autorizar/", views.autorizar, name="autorizar"),
    path("oauth/callback/", views.oauth_callback, name="oauth_callback"),
    path("desconectar/", views.desconectar, name="desconectar"),
]
