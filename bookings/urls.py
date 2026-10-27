from django.urls import path

from .views import (
    BookingCancelView,
    BookingConfirmView,
    BookingDetailView,
    BookingHoldCreateView,
    BookingListCreateView,
    MyBookingListView,
)


urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("holds/", BookingHoldCreateView.as_view(), name="booking-hold-create"),
    path("my/", MyBookingListView.as_view(), name="my-bookings"),
    path(
        "<uuid:pk>/confirm/",
        BookingConfirmView.as_view(),
        name="booking-confirm",
    ),
    path("<uuid:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<uuid:pk>/", BookingDetailView.as_view(), name="booking-detail"),
]
