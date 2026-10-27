from django.urls import path

from .views import (
    ScreenDetailView,
    ScreenLayoutView,
    ScreenListCreateView,
    ScreenSeatListView,
    CustomerShowDiscoveryView,
    ShowDetailView,
    ShowListCreateView,
    ShowSeatListView,
    ShowSeatPriceView,
)


urlpatterns = [
    path("discover/", CustomerShowDiscoveryView.as_view(), name="show-discover"),
    path("", ShowListCreateView.as_view(), name="show-list-create"),
    path(
        "<int:show_id>/prices/",
        ShowSeatPriceView.as_view(),
        name="show-seat-prices",
    ),
    path(
        "<int:show_id>/seats/",
        ShowSeatListView.as_view(),
        name="show-seat-list",
    ),
    path("<int:pk>/", ShowDetailView.as_view(), name="show-detail"),
    path("screens/", ScreenListCreateView.as_view(), name="screen-list-create"),
    path(
        "screens/<int:pk>/configure-layout/",
        ScreenLayoutView.as_view(),
        name="screen-configure-layout",
    ),
    path(
        "screens/<int:pk>/seats/",
        ScreenSeatListView.as_view(),
        name="screen-seat-list",
    ),
    path("screens/<int:pk>/", ScreenDetailView.as_view(), name="screen-detail"),
]
