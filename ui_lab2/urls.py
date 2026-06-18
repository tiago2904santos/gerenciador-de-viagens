from django.urls import path

from . import views

app_name = "ui_lab2"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.category, name="category"),
]
