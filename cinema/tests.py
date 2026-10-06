from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Cinema


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CinemaPermissionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser(
            username="platformadmin",
            email="platformadmin@example.com",
            password="Cinema-Password-42!",
        )
        self.tenant_admin = User.objects.create_user(
            username="cinemaowner",
            email="owner@example.com",
            password="Cinema-Password-42!",
            role=User.Role.TENANT_ADMIN,
        )
        self.other_tenant_admin = User.objects.create_user(
            username="otherowner",
            email="otherowner@example.com",
            password="Cinema-Password-42!",
            role=User.Role.TENANT_ADMIN,
        )
        self.user = User.objects.create_user(
            username="moviegoer",
            email="moviegoer@example.com",
            password="Cinema-Password-42!",
        )
        self.own_cinema = self.create_cinema(
            "My Cinema",
            self.tenant_admin,
            Cinema.Status.ACTIVE,
        )
        self.other_active_cinema = self.create_cinema(
            "Other Active Cinema",
            self.other_tenant_admin,
            Cinema.Status.ACTIVE,
        )
        self.pending_cinema = self.create_cinema(
            "Pending Cinema",
            self.create_tenant_admin("pendingowner"),
            Cinema.Status.PENDING,
        )

    def create_tenant_admin(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Cinema-Password-42!",
            role=User.Role.TENANT_ADMIN,
        )

    def create_cinema(self, name, owner, status):
        slug = name.lower().replace(" ", "-")
        schema_name = slug.replace("-", "_")
        return Cinema.objects.create(
            name=name,
            domain=f"{slug}.example.com",
            slug=slug,
            schema_name=schema_name,
            owner=owner,
            status=status,
        )

    def test_list_visibility_is_scoped_by_role(self):
        cases = (
            (self.super_admin, {"My Cinema", "Other Active Cinema", "Pending Cinema"}),
            (self.tenant_admin, {"My Cinema"}),
            (self.user, {"My Cinema", "Other Active Cinema"}),
        )

        for user, expected_names in cases:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.get("/api/cinemas/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {cinema["name"] for cinema in response.data},
                    expected_names,
                )

    def test_users_can_only_view_active_cinemas(self):
        self.client.force_authenticate(self.user)

        active_response = self.client.get(f"/api/cinemas/{self.own_cinema.pk}/")
        pending_response = self.client.get(f"/api/cinemas/{self.pending_cinema.pk}/")

        self.assertEqual(active_response.status_code, 200)
        self.assertEqual(pending_response.status_code, 403)

    def test_tenant_admin_can_view_and_update_only_own_cinema(self):
        self.client.force_authenticate(self.tenant_admin)

        own_response = self.client.get(f"/api/cinemas/{self.own_cinema.pk}/")
        other_response = self.client.get(
            f"/api/cinemas/{self.other_active_cinema.pk}/"
        )
        update_response = self.client.patch(
            f"/api/cinemas/{self.own_cinema.pk}/",
            {"address": "Updated address"},
            format="json",
        )
        other_update_response = self.client.patch(
            f"/api/cinemas/{self.other_active_cinema.pk}/",
            {"address": "Unauthorized address"},
            format="json",
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["address"], "Updated address")
        self.assertEqual(other_update_response.status_code, 403)

    def test_only_super_admin_can_create_and_delete_through_crud_endpoints(self):
        payload = {
            "username": "newowner",
            "email": "newowner@example.com",
            "password": "Cinema-Password-42!",
            "name": "New Cinema",
            "domain": "new.example.com",
        }

        self.client.force_authenticate(self.tenant_admin)
        tenant_response = self.client.post(
            "/api/cinemas/",
            payload,
            format="json",
        )
        self.client.force_authenticate(self.user)
        user_response = self.client.post(
            "/api/cinemas/",
            {**payload, "username": "newowner2", "email": "newowner2@example.com"},
            format="json",
        )

        self.assertEqual(tenant_response.status_code, 403)
        self.assertEqual(user_response.status_code, 403)
        self.assertFalse(User.objects.filter(username="newowner").exists())
        self.assertFalse(User.objects.filter(username="newowner2").exists())

        self.client.force_authenticate(self.tenant_admin)
        tenant_delete_response = self.client.delete(
            f"/api/cinemas/{self.own_cinema.pk}/"
        )
        self.client.force_authenticate(self.super_admin)
        delete_response = self.client.delete(
            f"/api/cinemas/{self.own_cinema.pk}/"
        )

        self.assertEqual(tenant_delete_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Cinema.objects.filter(pk=self.own_cinema.pk).exists())

    def test_super_admin_can_create_and_update_cinema(self):
        self.client.force_authenticate(self.super_admin)
        create_response = self.client.post(
            "/api/cinemas/",
            {
                "username": "createdowner",
                "email": "createdowner@example.com",
                "password": "Cinema-Password-42!",
                "name": "Created Cinema",
                "domain": "created.example.com",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        created_id = create_response.data["id"]
        update_response = self.client.patch(
            f"/api/cinemas/{created_id}/",
            {"address": "Platform updated"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["address"], "Platform updated")

    def test_only_super_admin_can_approve_or_reject(self):
        self.client.force_authenticate(self.tenant_admin)
        self.assertEqual(
            self.client.post(
                f"/api/cinemas/{self.own_cinema.pk}/approve/"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/api/cinemas/{self.own_cinema.pk}/reject/"
            ).status_code,
            403,
        )

        self.client.force_authenticate(self.super_admin)
        approve_response = self.client.post(
            f"/api/cinemas/{self.pending_cinema.pk}/approve/"
        )
        reject_response = self.client.post(
            f"/api/cinemas/{self.own_cinema.pk}/reject/"
        )

        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], Cinema.Status.ACTIVE)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.data["status"], Cinema.Status.REJECTED)
