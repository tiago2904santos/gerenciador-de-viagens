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
        path("dev/ui-lab/", views.ui_lab_index, name="ui_lab"),
        path("dev/ui-lab/structures/", views.ui_lab_structures, name="ui_lab_structures"),
        path("dev/ui-lab/lists/", views.ui_lab_lists, name="ui_lab_lists"),
        path("dev/ui-lab/headers/", views.ui_lab_headers, name="ui_lab_headers"),
        path("dev/ui-lab/buttons/", views.ui_lab_buttons, name="ui_lab_buttons"),
        path("dev/ui-lab/fields/", views.ui_lab_fields, name="ui_lab_fields"),
        path("dev/ui-lab/selects-filters/", views.ui_lab_selects_filters, name="ui_lab_selects_filters"),
        path("dev/ui-lab/status/", views.ui_lab_status, name="ui_lab_status"),
        path("dev/ui-lab/feedback/", views.ui_lab_feedback, name="ui_lab_feedback"),
        path("dev/ui-lab/cards/", views.ui_lab_cards, name="ui_lab_cards"),
        path("dev/ui-lab/overlays/", views.ui_lab_overlays, name="ui_lab_overlays"),
        path("dev/ui-lab/tables/", views.ui_lab_tables, name="ui_lab_tables"),
        path("dev/ui-lab/documents/", views.ui_lab_documents, name="ui_lab_documents"),
        path("dev/ui-lab/signature/", views.ui_lab_signature, name="ui_lab_signature"),
    ]
