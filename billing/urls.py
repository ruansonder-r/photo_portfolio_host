from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("new/", views.document_form, name="document_create"),

    # Literal prefixes before the UUID patterns, matching albums/urls.py.
    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_form, name="client_create"),
    path("clients/<uuid:pk>/", views.client_detail, name="client_detail"),
    path("clients/<uuid:pk>/edit/", views.client_form, name="client_edit"),
    path("settings/", views.settings_form, name="settings"),

    path("<uuid:pk>/", views.document_detail, name="document_detail"),
    path("<uuid:pk>/edit/", views.document_form, name="document_edit"),
    path("<uuid:pk>/pdf/", views.document_pdf, name="document_pdf"),
    path("<uuid:pk>/delete/", views.document_delete, name="document_delete"),
    path("<uuid:pk>/<slug:action>/", views.document_action, name="document_action"),
]
