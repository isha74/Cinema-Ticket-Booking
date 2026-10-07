from django.urls import path

from .views import ScreenDetailView, ScreenListCreateView


urlpatterns = [
    path("", ScreenListCreateView.as_view(), name="screen-list-create"),
    path("<int:pk>/", ScreenDetailView.as_view(), name="screen-detail-update-delete"),
]
