from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cinema.models import Cinema
from cinema.schema import cinema_schema
from movies.models import Movie
from movies.schema import ensure_movie_table
from shows.models import Screen, Seat, Show, ShowSeatPrice

from .models import Booking, BookingSeat


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BookingAPITests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="bookingcustomer",
            email="bookingcustomer@example.com",
            password="strong-test-password",
            role=User.Role.USER,
        )
        self.tenant_admin = User.objects.create_user(
            username="bookingowner",
            email="bookingowner@example.com",
            password="strong-test-password",
            role=User.Role.TENANT_ADMIN,
        )
        self.cinema = Cinema.objects.create(
            name="Booking Cinema",
            domain="booking.example.com",
            slug="booking-cinema",
            schema_name="booking_cinema",
            owner=self.tenant_admin,
            status=Cinema.Status.ACTIVE,
        )
        self.show_date = timezone.localdate() + timedelta(days=1)
        ensure_movie_table(self.cinema.schema_name)
        with cinema_schema(self.cinema.schema_name):
            self.screen = Screen.objects.create(
                cinema=self.cinema,
                name="Screen 1",
                total_seats=2,
            )
            self.seats = [
                Seat.objects.create(
                    screen=self.screen,
                    row="A",
                    seat_number=f"A{index}",
                    position=index,
                    seat_type="NORMAL",
                )
                for index in (1, 2)
            ]
            self.movie = Movie.objects.create(
                cinema=self.cinema,
                title="Booking Movie",
                duration=120,
                language="English",
                genre="Drama",
                release_date="2026-01-01",
                status=Movie.Status.ACTIVE,
            )
            self.show = Show.objects.create(
                movie=self.movie,
                screen=self.screen,
                show_date=self.show_date,
                start_time="14:00:00",
                end_time="16:00:00",
            )
            ShowSeatPrice.objects.create(
                show=self.show,
                seat_type="NORMAL",
                price=Decimal("190.00"),
            )
        self.client = APIClient()
        self.client.force_authenticate(self.customer)

    def create_booking(self, seats=None):
        return self.client.post(
            "/api/bookings/",
            {
                "cinema_slug": self.cinema.slug,
                "show": self.show.pk,
                "seats": seats or [seat.pk for seat in self.seats],
            },
            format="json",
        )

    def test_customer_can_book_seats_at_show_price_and_see_ticket_reference(self):
        response = self.create_booking()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total_amount"], "380.00")
        self.assertTrue(response.data["booking_reference"].startswith("CB-"))
        self.assertEqual(response.data["status"], Booking.Status.CONFIRMED)
        self.assertEqual(
            {seat["price_at_booking"] for seat in response.data["seats"]},
            {"190.00"},
        )

        with cinema_schema(self.cinema.schema_name):
            self.assertEqual(Booking.objects.count(), 1)
            self.assertEqual(BookingSeat.objects.filter(is_active=True).count(), 2)

    def test_seats_are_reserved_per_show_and_report_availability(self):
        booking = self.create_booking(seats=[self.seats[0].pk])
        self.assertEqual(booking.status_code, 201)

        availability = self.client.get(
            f"/api/shows/{self.show.pk}/seats/",
            {"cinema_slug": self.cinema.slug},
        )
        self.assertEqual(availability.status_code, 200)
        states = {seat["seat_number"]: seat["is_available"] for seat in availability.data}
        self.assertEqual(states, {"A1": False, "A2": True})

        repeated_booking = self.create_booking(seats=[self.seats[0].pk])
        self.assertEqual(repeated_booking.status_code, 409)

    def test_customer_can_hold_seats_and_confirm_without_payment(self):
        hold = self.client.post(
            "/api/bookings/holds/",
            {
                "cinema_slug": self.cinema.slug,
                "show": self.show.pk,
                "seats": [self.seats[0].pk],
            },
            format="json",
        )

        self.assertEqual(hold.status_code, 201, hold.data)
        self.assertEqual(hold.data["status"], Booking.Status.HELD)
        self.assertEqual(hold.data["total_amount"], "190.00")
        self.assertIsNotNone(hold.data["hold_expires_at"])

        availability = self.client.get(
            f"/api/shows/{self.show.pk}/seats/",
            {"cinema_slug": self.cinema.slug},
        )
        states = {
            seat["seat_number"]: seat["status"]
            for seat in availability.data
        }
        self.assertEqual(states, {"A1": "HELD", "A2": "AVAILABLE"})

        duplicate_hold = self.client.post(
            "/api/bookings/holds/",
            {
                "cinema_slug": self.cinema.slug,
                "show": self.show.pk,
                "seats": [self.seats[0].pk],
            },
            format="json",
        )
        self.assertEqual(duplicate_hold.status_code, 409)

        confirmed = self.client.post(
            f"/api/bookings/{hold.data['id']}/confirm/",
            {},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.data["status"], Booking.Status.CONFIRMED)
        states = {
            seat["seat_number"]: seat["status"]
            for seat in self.client.get(
                f"/api/shows/{self.show.pk}/seats/",
                {"cinema_slug": self.cinema.slug},
            ).data
        }
        self.assertEqual(states["A1"], "BOOKED")

    def test_expired_holds_release_seats_and_cannot_be_confirmed(self):
        hold = self.client.post(
            "/api/bookings/holds/",
            {
                "cinema_slug": self.cinema.slug,
                "show": self.show.pk,
                "seats": [self.seats[0].pk],
            },
            format="json",
        )
        self.assertEqual(hold.status_code, 201)

        with cinema_schema(self.cinema.schema_name):
            Booking.objects.filter(pk=hold.data["id"]).update(
                hold_expires_at=timezone.now() - timedelta(seconds=1),
            )

        availability = self.client.get(
            f"/api/shows/{self.show.pk}/seats/",
            {"cinema_slug": self.cinema.slug},
        )
        self.assertEqual(availability.data[0]["status"], "AVAILABLE")
        self.assertTrue(availability.data[0]["is_available"])

        confirmation = self.client.post(
            f"/api/bookings/{hold.data['id']}/confirm/",
            {},
            format="json",
        )
        self.assertEqual(confirmation.status_code, 410)
        with cinema_schema(self.cinema.schema_name):
            self.assertEqual(
                Booking.objects.get(pk=hold.data["id"]).status,
                Booking.Status.EXPIRED,
            )

    def test_same_screen_seat_can_be_booked_for_another_show(self):
        with cinema_schema(self.cinema.schema_name):
            second_show = Show.objects.create(
                movie=self.movie,
                screen=self.screen,
                show_date=self.show_date,
                start_time="18:00:00",
                end_time="20:00:00",
            )
            ShowSeatPrice.objects.create(
                show=second_show,
                seat_type="NORMAL",
                price=Decimal("220.00"),
            )
        first_booking = self.create_booking(seats=[self.seats[0].pk])
        second_booking = self.client.post(
            "/api/bookings/",
            {
                "cinema_slug": self.cinema.slug,
                "show": second_show.pk,
                "seats": [self.seats[0].pk],
            },
            format="json",
        )

        self.assertEqual(first_booking.status_code, 201)
        self.assertEqual(second_booking.status_code, 201)
        self.assertEqual(second_booking.data["total_amount"], "220.00")

    def test_cancelling_booking_releases_seats_and_preserves_booking(self):
        booking = self.create_booking(seats=[self.seats[0].pk])
        cancellation = self.client.post(
            f"/api/bookings/{booking.data['id']}/cancel/",
            {},
            format="json",
        )

        self.assertEqual(cancellation.status_code, 200)
        self.assertEqual(cancellation.data["status"], Booking.Status.CANCELLED)
        availability = self.client.get(
            f"/api/shows/{self.show.pk}/seats/",
            {"cinema_slug": self.cinema.slug},
        )
        self.assertTrue(availability.data[0]["is_available"])
        self.assertEqual(
            self.client.get(f"/api/bookings/{booking.data['id']}/").status_code,
            200,
        )

    def test_customer_must_select_an_active_cinema_and_valid_show_seats(self):
        no_cinema = self.client.post(
            "/api/bookings/",
            {"show": self.show.pk, "seats": [self.seats[0].pk]},
            format="json",
        )
        invalid_seat = self.create_booking(seats=[999999])

        self.assertEqual(no_cinema.status_code, 400)
        self.assertEqual(invalid_seat.status_code, 400)

    def test_only_regular_customers_can_create_or_manage_bookings(self):
        self.client.force_authenticate(self.tenant_admin)

        create_response = self.create_booking(seats=[self.seats[0].pk])
        list_response = self.client.get("/api/bookings/my/")

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(list_response.status_code, 403)

    def test_customer_booking_list_is_limited_to_the_authenticated_user(self):
        own_booking = self.create_booking(seats=[self.seats[0].pk])
        other_user = User.objects.create_user(
            username="secondcustomer",
            email="secondcustomer@example.com",
            password="strong-test-password",
            role=User.Role.USER,
        )
        with cinema_schema(self.cinema.schema_name):
            booking = Booking.objects.get(pk=own_booking.data["id"])
            Booking.objects.create(
                user=other_user,
                show=booking.show,
                total_amount=Decimal("190.00"),
            )

        list_response = self.client.get("/api/bookings/my/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)

    def test_tenant_cannot_delete_screen_or_movie_with_booking_history(self):
        booking = self.create_booking(seats=[self.seats[0].pk])
        self.assertEqual(booking.status_code, 201)
        self.client.force_authenticate(self.tenant_admin)

        screen_response = self.client.delete(
            f"/api/shows/screens/{self.screen.pk}/"
        )
        movie_response = self.client.delete(f"/api/movies/{self.movie.pk}/")

        self.assertEqual(screen_response.status_code, 409)
        self.assertEqual(movie_response.status_code, 409)
