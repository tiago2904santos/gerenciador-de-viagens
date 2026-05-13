from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
]

if settings.DEBUG:
    urlpatterns += [
        path("dev/ui-lab/", views.ui_lab, name="ui_lab"),
    ]
