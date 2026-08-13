from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("metrics/", views.metrics, name="metrics"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    path("", views.dashboard, name="dashboard"),
]
