from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from cinema.models import Cinema

from .models import Movie
from .schema import allocate_movie_id, cinema_schema, ensure_movie_table


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MovieAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.super_admin = User.objects.create_superuser(
            username="platformadmin",
            email="platformadmin@example.com",
            password="Cinema-Password-42!",
        )
        self.tenant_admin = self.create_user("cinemaowner", User.Role.TENANT_ADMIN)
        self.other_tenant_admin = self.create_user(
            "otherowner",
            User.Role.TENANT_ADMIN,
        )
        self.user = self.create_user("moviegoer", User.Role.USER)
        self.cinema = self.create_cinema("My Cinema", self.tenant_admin)
        self.other_cinema = self.create_cinema(
            "Other Cinema",
            self.other_tenant_admin,
        )
        self.inactive_cinema = self.create_cinema(
            "Inactive Cinema",
            self.create_user("inactiveowner", User.Role.TENANT_ADMIN),
            Cinema.Status.PENDING,
        )
        self.movie = self.create_movie(self.cinema, "Active Movie")
        self.other_movie = self.create_movie(self.other_cinema, "Other Movie")
        self.inactive_movie = self.create_movie(
            self.inactive_cinema,
            "Hidden Movie",
        )
        self.inactive_movie.status = Movie.Status.INACTIVE
        with cinema_schema(self.inactive_cinema.schema_name):
            self.inactive_movie.save(update_fields=["status"])

    def create_user(self, username, role):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Cinema-Password-42!",
            role=role,
        )

    def create_cinema(self, name, owner, status=Cinema.Status.ACTIVE):
        slug = name.lower().replace(" ", "-")
        schema_name = slug.replace("-", "_")
        if connection.vendor == "postgresql":
            quoted_schema = connection.ops.quote_name(schema_name)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
        return Cinema.objects.create(
            name=name,
            domain=f"{slug}.example.com",
            slug=slug,
            schema_name=schema_name,
            owner=owner,
            status=status,
        )

    def create_movie(
        self,
        cinema,
        title,
        status=Movie.Status.ACTIVE,
        movie_id=None,
    ):
        ensure_movie_table(cinema.schema_name)
        with cinema_schema(cinema.schema_name):
            movie_id = movie_id or allocate_movie_id()
            return Movie.objects.create(
                **({"id": movie_id} if movie_id else {}),
                cinema=cinema,
                title=title,
                description=f"Description for {title}",
                duration=120,
                language="English",
                genre="Drama",
                release_date=date(2026, 1, 15),
                status=status,
            )

    def movie_payload(self, cinema=None, title="New Movie"):
        return {
            "title": title,
            "description": "A sample movie description.",
            "duration": 125,
            "language": "English",
            "genre": "Drama",
            "release_date": "2026-02-10",
        }

    def test_list_is_scoped_to_each_role(self):
        cases = (
            (self.super_admin, {"Active Movie", "Other Movie", "Hidden Movie"}),
            (self.tenant_admin, {"Active Movie"}),
            (self.user, {"Active Movie", "Other Movie"}),
        )

        for user, expected_titles in cases:
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.get("/api/movies/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {movie["title"] for movie in response.data},
                    expected_titles,
                )

    def test_super_admin_can_list_movies_for_selected_cinema_schema(self):
        self.client.force_authenticate(self.super_admin)

        response = self.client.get(
            "/api/movies/",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {movie["title"] for movie in response.data},
            {"Other Movie"},
        )

    def test_superuser_with_user_role_still_sees_draft_movies(self):
        self.movie.status = Movie.Status.DRAFT
        with cinema_schema(self.cinema.schema_name):
            self.movie.save(update_fields=["status"])
        self.super_admin.role = User.Role.USER
        self.super_admin.save(update_fields=["role"])
        self.client.force_authenticate(self.super_admin)

        response = self.client.get(
            "/api/movies/",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {movie["title"] for movie in response.data},
            {"Active Movie"},
        )
        self.assertEqual(response.data[0]["status"], Movie.Status.DRAFT)

    def test_tenant_admin_can_list_only_own_schema_and_cannot_select_another(self):
        self.client.force_authenticate(self.tenant_admin)

        own_response = self.client.get(
            "/api/movies/",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )
        other_response = self.client.get(
            "/api/movies/",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(
            {movie["title"] for movie in own_response.data},
            {"Active Movie"},
        )
        self.assertEqual(other_response.status_code, 403)

    def test_selected_schema_without_movie_table_returns_clear_error(self):
        if connection.vendor != "postgresql":
            self.skipTest("Separate cinema schemas require PostgreSQL.")

        owner = self.create_user("tablemissingowner", User.Role.TENANT_ADMIN)
        cinema = self.create_cinema("Table Missing Cinema", owner)
        self.client.force_authenticate(self.super_admin)

        response = self.client.get(
            "/api/movies/",
            HTTP_X_SCHEMA_NAME=cinema.schema_name,
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("movies_movie table is missing", response.data["detail"])

    def test_tenant_admin_can_create_and_update_movie_for_own_cinema(self):
        self.client.force_authenticate(self.tenant_admin)
        create_response = self.client.post(
            "/api/movies/",
            self.movie_payload(),
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], Movie.Status.DRAFT)

        movie_id = create_response.data["id"]
        with cinema_schema(self.cinema.schema_name):
            self.assertTrue(
                Movie.objects.filter(pk=movie_id, cinema_id=self.cinema.pk).exists()
            )
        with cinema_schema(self.other_cinema.schema_name):
            self.assertFalse(
                Movie.objects.filter(pk=movie_id, cinema_id=self.cinema.pk).exists()
            )

        update_response = self.client.patch(
            f"/api/movies/{movie_id}/",
            {"duration": 130, "status": Movie.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["duration"], 130)
        self.assertEqual(update_response.data["status"], Movie.Status.ACTIVE)

    def test_movie_ids_are_allocated_across_cinema_schemas(self):
        if connection.vendor != "postgresql":
            self.skipTest("Separate cinema schemas require PostgreSQL.")

        self.assertNotEqual(self.movie.pk, self.other_movie.pk)

    def test_tenant_admin_can_replace_and_delete_own_movie(self):
        self.client.force_authenticate(self.tenant_admin)
        put_response = self.client.put(
            f"/api/movies/{self.movie.pk}/",
            self.movie_payload(self.cinema, "Replaced Movie"),
            format="json",
        )
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.data["title"], "Replaced Movie")

        delete_response = self.client.delete(f"/api/movies/{self.movie.pk}/")
        self.assertEqual(delete_response.status_code, 204)
        with cinema_schema(self.cinema.schema_name):
            self.assertFalse(Movie.objects.filter(pk=self.movie.pk).exists())

    def test_tenant_admin_cannot_manage_another_cinemas_movies(self):
        self.client.force_authenticate(self.tenant_admin)

        create_response = self.client.post(
            "/api/movies/",
            self.movie_payload(title="Unauthorized Movie"),
            format="json",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )
        detail_response = self.client.get(f"/api/movies/{self.other_movie.pk}/")
        update_response = self.client.patch(
            f"/api/movies/{self.other_movie.pk}/",
            {"title": "Changed by wrong tenant"},
            format="json",
        )
        delete_response = self.client.delete(f"/api/movies/{self.other_movie.pk}/")

        self.assertEqual(create_response.status_code, 403)
        expected_status = (
            409 if self.movie.pk == self.other_movie.pk else 403
        )
        self.assertEqual(detail_response.status_code, expected_status)
        self.assertEqual(update_response.status_code, expected_status)
        self.assertEqual(delete_response.status_code, expected_status)

    def test_user_can_read_active_movies_but_cannot_change_them(self):
        self.client.force_authenticate(self.user)

        detail_response = self.client.get(f"/api/movies/{self.movie.pk}/")
        update_response = self.client.patch(
            f"/api/movies/{self.movie.pk}/",
            {"title": "Changed by user"},
            format="json",
        )
        delete_response = self.client.delete(f"/api/movies/{self.movie.pk}/")

        expected_detail_status = (
            409 if self.movie.pk == self.other_movie.pk else 200
        )
        self.assertEqual(detail_response.status_code, expected_detail_status)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_super_admin_cannot_create_update_or_delete_movies(self):
        self.client.force_authenticate(self.super_admin)
        create_response = self.client.post(
            "/api/movies/",
            self.movie_payload(title="Admin Movie"),
            format="json",
        )
        update_response = self.client.patch(
            f"/api/movies/{self.other_movie.pk}/",
            {"title": "Changed by super admin"},
            format="json",
        )
        delete_response = self.client.delete(f"/api/movies/{self.other_movie.pk}/")

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    def test_super_admin_can_read_all_movies(self):
        self.client.force_authenticate(self.super_admin)
        response = self.client.get("/api/movies/")
        detail_response = self.client.get(f"/api/movies/{self.other_movie.pk}/")

        self.assertEqual(response.status_code, 200)
        expected_detail_status = (
            409
            if connection.vendor == "postgresql"
            and self.movie.pk == self.other_movie.pk
            else 200
        )
        self.assertEqual(detail_response.status_code, expected_detail_status)

    def test_duplicate_ids_across_schemas_are_reported_as_ambiguous(self):
        if connection.vendor != "postgresql":
            self.skipTest("Separate cinema schemas require PostgreSQL.")

        self.create_movie(
            self.other_cinema,
            "Duplicate ID Movie",
            movie_id=self.movie.pk,
        )
        self.client.force_authenticate(self.super_admin)

        response = self.client.get(f"/api/movies/{self.movie.pk}/")

        self.assertEqual(response.status_code, 409)

    def test_registration_status_is_always_draft(self):
        self.client.force_authenticate(self.tenant_admin)
        response = self.client.post(
            "/api/movies/",
            {
                **self.movie_payload(self.cinema),
                "status": Movie.Status.ACTIVE,
            },
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Movie.Status.DRAFT)

    def test_duration_must_be_positive(self):
        self.client.force_authenticate(self.tenant_admin)
        response = self.client.post(
            "/api/movies/",
            {**self.movie_payload(), "duration": 0},
            format="json",
            HTTP_X_SCHEMA_NAME=self.cinema.schema_name,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("duration", response.data)

    def test_movie_registration_requires_owned_schema_header(self):
        self.client.force_authenticate(self.tenant_admin)

        missing_header_response = self.client.post(
            "/api/movies/",
            self.movie_payload(),
            format="json",
        )
        wrong_schema_response = self.client.post(
            "/api/movies/",
            self.movie_payload(),
            format="json",
            HTTP_X_SCHEMA_NAME=self.other_cinema.schema_name,
        )

        self.assertEqual(missing_header_response.status_code, 400)
        self.assertIn("X-Schema-Name", missing_header_response.data)
        self.assertEqual(wrong_schema_response.status_code, 403)
