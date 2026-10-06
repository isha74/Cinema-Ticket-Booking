from django.urls import path

from .views import (
    CinemaApproveView,
    CinemaDetailView,
    CinemaListCreateView,
    CinemaRegistrationView,
    CinemaRejectView,
)


urlpatterns = [
    #tenant actions
    path("register/", CinemaRegistrationView.as_view(), name="cinema-register"),
    path("", CinemaListCreateView.as_view(), name="cinema-list-create"),
    path("<int:pk>/", CinemaDetailView.as_view(), name="cinema-detail-update-delete"),
    
    #admin actions
    path("<int:pk>/approve/", CinemaApproveView.as_view(), name="cinema-approve"),
    path("<int:pk>/reject/", CinemaRejectView.as_view(), name="cinema-reject"),
]
