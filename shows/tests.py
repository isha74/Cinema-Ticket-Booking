from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from cinema.models import Cinema
from movies.models import Movie
from movies.schema import ensure_movie_table

from .models import Screen, Seat, Show, ShowSeatPrice
from .schema import cinema_schema, ensure_screen_tables


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ShowWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_admin = User.objects.create_user(
            username="showowner",
            email="showowner@example.com",
            password="test-password-123",
            role=User.Role.TENANT_ADMIN,
        )
        self.other_tenant_admin = User.objects.create_user(
            username="otherowner",
            email="otherowner@example.com",
            password="test-password-123",
            role=User.Role.TENANT_ADMIN,
        )
        self.super_admin = User.objects.create_superuser(
            username="platformadmin",
            email="platformadmin@example.com",
            password="test-password-123",
        )
        self.user = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="test-password-123",
            role=User.Role.USER,
        )
        self.cinema = self.create_cinema("Main Cinema", self.tenant_admin)
        self.other_cinema = self.create_cinema(
            "Other Cinema",
            self.other_tenant_admin,
        )
        ensure_screen_tables(self.cinema.schema_name)
        ensure_screen_tables(self.other_cinema.schema_name)
        ensure_movie_table(self.cinema.schema_name)
        ensure_movie_table(self.other_cinema.schema_name)
        with cinema_schema(self.cinema.schema_name):
            self.screen = Screen.objects.create(
                cinema=self.cinema,
                name="Screen 1",
                total_seats=4,
            )
            self.movie = Movie.objects.create(
                cinema=self.cinema,
                title="Example Movie",
                duration=120,
                language="English",
                genre="Drama",
                release_date="2026-01-01",
                status=Movie.Status.ACTIVE,
            )
        with cinema_schema(self.other_cinema.schema_name):
            self.other_screen = Screen.objects.create(
                id=999,
                cinema=self.other_cinema,
                name="Other Screen",
                total_seats=4,
            )
            self.other_movie = Movie.objects.create(
                id=999,
                cinema=self.other_cinema,
                title="Other Movie",
                duration=100,
                language="English",
                genre="Drama",
                release_date="2026-01-01",
                status=Movie.Status.ACTIVE,
            )
        self.client.force_authenticate(self.tenant_admin)

    def create_cinema(self, name, owner):
        slug = name.lower().replace(" ", "-")
        return Cinema.objects.create(
            name=name,
            domain=f"{slug}.example.com",
            slug=slug,
            schema_name=slug.replace("-", "_"),
            owner=owner,
            status=Cinema.Status.ACTIVE,
        )

    def configure_layout(self, screen=None):
        screen = screen or self.screen
        return self.client.post(
            f"/api/shows/screens/{screen.pk}/configure-layout/",
            {
                "rows": [
                    {
                        "label": "A",
                        "seat_count": 2,
                        "seat_type": "NORMAL",
                        "gaps_after": [1],
                    },
                    {"label": "B", "seat_count": 2, "seat_type": "GOLD"},
                ]
            },
            format="json",
        )

    def create_show(self, *, start="14:00:00", end="16:00:00", movie=None):
        return self.client.post(
            "/api/shows/",
            {
                "movie": (movie or self.movie).pk,
                "screen": self.screen.pk,
                "show_date": "2026-10-20",
                "start_time": start,
                "end_time": end,
            },
            format="json",
        )

    def test_configures_permanent_layout_and_rejects_reconfiguration(self):
        response = self.configure_layout()
        repeat_response = self.configure_layout()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["seat_count"], self.screen.total_seats)
        self.assertEqual(len(response.data["seats"]), 4)
        self.assertEqual(response.data["seats"][1]["position"], 3)
        self.assertEqual(response.data["seats"][2]["seat_type"], "GOLD")
        self.assertEqual(repeat_response.status_code, 409)
        with cinema_schema(self.cinema.schema_name):
            self.assertEqual(Seat.objects.filter(screen=self.screen).count(), 4)

    def test_layout_requires_exact_capacity(self):
        response = self.client.post(
            f"/api/shows/screens/{self.screen.pk}/configure-layout/",
            {
                "rows": [
                    {"label": "A", "seat_count": 3, "seat_type": "NORMAL"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        with cinema_schema(self.cinema.schema_name):
            self.assertFalse(Seat.objects.filter(screen=self.screen).exists())

    def test_show_and_prices_are_show_specific(self):
        self.configure_layout()
        afternoon = self.create_show()
        evening = self.create_show(start="18:00:00", end="20:00:00")

        self.assertEqual(afternoon.status_code, 201)
        self.assertEqual(evening.status_code, 201)
        afternoon_id = afternoon.data["id"]
        evening_id = evening.data["id"]

        afternoon_prices = self.client.put(
            f"/api/shows/{afternoon_id}/prices/",
            {
                "prices": [
                    {"seat_type": "NORMAL", "price": "150.00"},
                    {"seat_type": "GOLD", "price": "200.00"},
                ]
            },
            format="json",
        )
        evening_prices = self.client.put(
            f"/api/shows/{evening_id}/prices/",
            {
                "prices": [
                    {"seat_type": "NORMAL", "price": "190.00"},
                    {"seat_type": "GOLD", "price": "250.00"},
                ]
            },
            format="json",
        )

        self.assertEqual(afternoon_prices.status_code, 200)
        self.assertEqual(evening_prices.status_code, 200)
        afternoon_seats = self.client.get(f"/api/shows/{afternoon_id}/seats/")
        evening_seats = self.client.get(f"/api/shows/{evening_id}/seats/")
        self.assertEqual(afternoon_seats.status_code, 200)
        self.assertEqual(evening_seats.status_code, 200)
        self.assertEqual(
            {seat["price"] for seat in afternoon_seats.data},
            {Decimal("150.00"), Decimal("200.00")},
        )
        self.assertEqual(
            {seat["price"] for seat in evening_seats.data},
            {Decimal("190.00"), Decimal("250.00")},
        )
        with cinema_schema(self.cinema.schema_name):
            self.assertEqual(Seat.objects.filter(screen=self.screen).count(), 4)
            self.assertEqual(Show.objects.filter(screen=self.screen).count(), 2)
            self.assertEqual(ShowSeatPrice.objects.count(), 4)

    def test_show_requires_own_movie_screen_and_configured_layout(self):
        missing_layout_response = self.create_show()
        self.configure_layout()
        foreign_movie_response = self.create_show(movie=self.other_movie)
        foreign_screen_response = self.client.post(
            "/api/shows/",
            {
                "movie": self.movie.pk,
                "screen": self.other_screen.pk,
                "show_date": "2026-10-20",
                "start_time": "14:00:00",
                "end_time": "16:00:00",
            },
            format="json",
        )

        self.assertEqual(missing_layout_response.status_code, 400)
        self.assertEqual(foreign_movie_response.status_code, 400)
        self.assertEqual(foreign_screen_response.status_code, 400)

    def test_show_rejects_overlapping_schedule(self):
        self.configure_layout()
        first = self.create_show()
        overlap = self.create_show(start="15:30:00", end="17:00:00")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(overlap.status_code, 400)

    def test_show_prices_must_cover_each_category_exactly_once(self):
        self.configure_layout()
        show = self.create_show()
        response = self.client.put(
            f"/api/shows/{show.data['id']}/prices/",
            {"prices": [{"seat_type": "NORMAL", "price": "190.00"}]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_tenant_is_derived_from_authenticated_user_not_request_schema(self):
        self.configure_layout()
        response = self.client.get(
            "/api/shows/screens/",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([screen["id"] for screen in response.data], [self.screen.pk])

    def test_only_tenant_admin_can_use_show_and_layout_apis(self):
        paths = (
            ("/api/shows/screens/", "get"),
            (f"/api/shows/screens/{self.screen.pk}/configure-layout/", "post"),
            ("/api/shows/", "get"),
            ("/api/shows/", "post"),
        )
        for user in (self.super_admin, self.user):
            self.client.force_authenticate(user)
            for path, method in paths:
                with self.subTest(user=user.username, path=path):
                    response = getattr(self.client, method)(
                        path,
                        data={} if method == "post" else None,
                        format="json" if method == "post" else None,
                    )
                    self.assertEqual(response.status_code, 403)
