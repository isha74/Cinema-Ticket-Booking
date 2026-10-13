from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from cinema.models import Cinema

from .models import Screen
from .schema import cinema_schema, ensure_screen_tables


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScreenAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_admin = self.create_user("screenowner", User.Role.TENANT_ADMIN)
        self.other_tenant_admin = self.create_user("otherowner", User.Role.TENANT_ADMIN)
        self.super_admin = User.objects.create_superuser(
            username="platformadmin",
            email="platformadmin@example.com",
            password="Cinema-Password-42!",
        )
        self.user = self.create_user("moviegoer", User.Role.USER)
        self.cinema = self.create_cinema("Owner Cinema", self.tenant_admin)
        self.other_cinema = self.create_cinema(
            "Other Cinema",
            self.other_tenant_admin,
        )
        self.pending_cinema = self.create_cinema(
            "Pending Cinema",
            self.create_user("pendingowner", User.Role.TENANT_ADMIN),
            Cinema.Status.PENDING,
        )
        with cinema_schema(self.cinema.schema_name):
            self.own_screen = Screen.objects.create(
                cinema=self.cinema,
                name="Screen 1",
                total_seats=100,
            )
        with cinema_schema(self.other_cinema.schema_name):
            self.other_screen = Screen.objects.create(
                cinema=self.other_cinema,
                name="Screen 1",
                total_seats=80,
            )
        with cinema_schema(self.pending_cinema.schema_name):
            Screen.objects.create(
                cinema=self.pending_cinema,
                name="Pending Screen",
                total_seats=40,
            )

    def create_user(self, username, role):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Cinema-Password-42!",
            role=role,
        )

    def create_cinema(self, name, owner, status=Cinema.Status.ACTIVE):
        slug = name.lower().replace(" ", "-")
        cinema = Cinema.objects.create(
            name=name,
            domain=f"{slug}.example.com",
            slug=slug,
            schema_name=slug.replace("-", "_"),
            owner=owner,
            status=status,
        )
        ensure_screen_tables(cinema.schema_name)
        return cinema

    def test_tenant_admin_creates_screen_for_own_cinema_without_sending_cinema_id(self):
        self.client.force_authenticate(self.tenant_admin)

        response = self.client.post(
            "/api/screens/",
            {"name": "Screen 2", "total_seats": 120},
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["cinema"], self.cinema.pk)
        self.assertEqual(response.data["name"], "Screen 2")
        self.assertEqual(response.data["total_seats"], 120)

    def test_tenant_admin_can_list_only_own_screens(self):
        self.client.force_authenticate(self.tenant_admin)

        response = self.client.get(
            "/api/screens/",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([screen["id"] for screen in response.data], [self.own_screen.pk])

    def test_tenant_admin_can_update_and_delete_own_screen(self):
        self.client.force_authenticate(self.tenant_admin)

        update_response = self.client.patch(
            f"/api/screens/{self.own_screen.pk}/",
            {"total_seats": 110},
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )
        delete_response = self.client.delete(
            f"/api/screens/{self.own_screen.pk}/",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["total_seats"], 110)
        self.assertEqual(delete_response.status_code, 204)
        with cinema_schema(self.cinema.schema_name):
            self.assertFalse(Screen.objects.filter(pk=self.own_screen.pk).exists())

    def test_tenant_admin_cannot_access_or_manage_another_cinemas_screen(self):
        self.client.force_authenticate(self.tenant_admin)

        detail_response = self.client.get(
            f"/api/screens/{self.other_screen.pk}/",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )
        update_response = self.client.patch(
            f"/api/screens/{self.other_screen.pk}/",
            {"name": "Not allowed"},
            format="json",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )
        delete_response = self.client.delete(
            f"/api/screens/{self.other_screen.pk}/",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_super_admin_can_view_but_not_change_screens(self):
        self.client.force_authenticate(self.super_admin)

        list_response = self.client.get("/api/screens/")
        update_response = self.client.patch(
            f"/api/screens/{self.own_screen.pk}/",
            {"name": "Changed"},
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 3)
        self.assertEqual(update_response.status_code, 403)

    def test_regular_users_only_see_screens_for_active_cinemas(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/screens/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertNotIn(
            self.pending_cinema.pk,
            {screen["cinema"] for screen in response.data},
        )

    def test_screen_requires_positive_seat_count(self):
        self.client.force_authenticate(self.tenant_admin)

        response = self.client.post(
            "/api/screens/",
            {"name": "Invalid Screen", "total_seats": 0},
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("total_seats", response.data)

    def test_tenant_admin_must_select_their_cinema_schema(self):
        self.client.force_authenticate(self.tenant_admin)

        missing_header_response = self.client.get("/api/screens/")
        missing_create_header_response = self.client.post(
            "/api/screens/",
            {"name": "Missing Schema Screen", "total_seats": 50},
            format="json",
        )
        other_schema_response = self.client.post(
            "/api/screens/",
            {"name": "Wrong Cinema Screen", "total_seats": 50},
            format="json",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(missing_header_response.status_code, 400)
        self.assertIn("X-Schema-Name", missing_header_response.data)
        self.assertEqual(missing_create_header_response.status_code, 400)
        self.assertIn("X-Schema-Name", missing_create_header_response.data)
        self.assertEqual(other_schema_response.status_code, 403)

    def test_deleting_cinema_cleans_its_screens(self):
        cinema_schema_name = self.cinema.schema_name

        self.cinema.delete()

        with cinema_schema(cinema_schema_name):
            self.assertFalse(
                Screen.objects.filter(cinema_id=self.cinema.pk).exists()
            )
