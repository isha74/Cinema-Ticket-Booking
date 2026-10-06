from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from cinema.models import Cinema


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthenticationAPITests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.password = "Cinema-Password-42!"
		self.user = User.objects.create_user(
			username="moviegoer",
			email="moviegoer@example.com",
			password=self.password,
		)
		self.tenant_admin = User.objects.create_user(
			username="cinemaowner",
			email="owner@example.com",
			password=self.password,
			role=User.Role.TENANT_ADMIN,
		)
		self.superadmin = User.objects.create_superuser(
			username="platformadmin",
			email="admin@example.com",
			password=self.password,
		)

	def test_registration_assigns_normal_user_role_and_ignores_requested_role(self):
		response = self.client.post(
			"/api/auth/register/",
			{
				"username": "newmoviegoer",
				"email": "new@example.com",
				"password": self.password,
				"role": User.Role.SUPER_ADMIN,
			},
		)

		self.assertEqual(response.status_code, 201)
		created_user = User.objects.get(username="newmoviegoer")
		self.assertEqual(created_user.role, User.Role.USER)
		self.assertNotIn("password", response.data)

	def test_tenant_registration_requires_superadmin(self):
		response = self.client.post(
			"/api/auth/register/tenant/",
			{
				"username": "newcinema",
				"email": "newcinema@example.com",
				"password": self.password,
			},
		)

		self.assertEqual(response.status_code, 401)

		self.client.force_authenticate(self.superadmin)
		response = self.client.post(
			"/api/auth/register/tenant/",
			{
				"username": "newcinema",
				"email": "newcinema@example.com",
				"password": self.password,
			},
		)

		self.assertEqual(response.status_code, 201)
		created_user = User.objects.get(username="newcinema")
		self.assertEqual(created_user.role, User.Role.TENANT_ADMIN)
		self.assertFalse(created_user.is_staff)
		self.assertFalse(created_user.is_superuser)

	def test_cinema_registration_creates_tenant_admin(self):
		response = self.client.post(
			"/api/cinemas/register/",
			{
				"username": "galaxyowner",
				"email": "galaxy.admin@example.com",
				"password": self.password,
				"name": "Galaxy Cinema",
				"domain": "galaxy.example.com",
				"address": "Main Road",
				"city": "Pune",
				"contact_email": "hello@galaxy.example.com",
				"contact_phone": "9999999999",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 201)
		created_user = User.objects.get(email="galaxy.admin@example.com")
		self.assertEqual(created_user.username, "galaxyowner")
		self.assertEqual(created_user.role, User.Role.TENANT_ADMIN)
		self.assertEqual(response.data["domain"], "galaxy.example.com")
		self.assertEqual(response.data["status"], Cinema.Status.PENDING)
		self.assertEqual(response.data["schema_name"], "galaxy_example_com")
		self.assertEqual(response.data["tenant_admin"]["role"], User.Role.TENANT_ADMIN)

	def test_superadmin_can_approve_and_reject_cinema(self):
		response = self.client.post(
			"/api/cinemas/register/",
			{
				"username": "approvalowner",
				"email": "approval@example.com",
				"password": "password",
				"name": "Approval Cinema",
				"domain": "approval.example.com",
			},
			format="json",
		)
		cinema_id = response.data["id"]

		self.client.force_authenticate(self.user)
		self.assertEqual(
			self.client.post(f"/api/cinemas/{cinema_id}/approve/").status_code,
			403,
		)

		self.client.force_authenticate(self.superadmin)
		approve_response = self.client.post(f"/api/cinemas/{cinema_id}/approve/")
		self.assertEqual(approve_response.status_code, 200)
		self.assertEqual(approve_response.data["status"], Cinema.Status.ACTIVE)

		reject_response = self.client.post(f"/api/cinemas/{cinema_id}/reject/")
		self.assertEqual(reject_response.status_code, 200)
		self.assertEqual(reject_response.data["status"], Cinema.Status.REJECTED)

	def test_login_returns_tokens_with_role_claim(self):
		response = self.client.post(
			"/api/auth/login/",
			{"username": self.tenant_admin.username, "password": self.password},
		)

		self.assertEqual(response.status_code, 200)
		token = AccessToken(response.data["access"])
		self.assertEqual(token["role"], User.Role.TENANT_ADMIN)

	def test_superuser_is_created_with_superadmin_role(self):
		self.assertEqual(self.superadmin.role, User.Role.SUPER_ADMIN)

	def test_user_details_are_only_available_to_superadmins(self):
		self.client.force_authenticate(self.user)
		self.assertEqual(
			self.client.get(f"/api/auth/{self.tenant_admin.id}/").status_code,
			403,
		)

		self.client.force_authenticate(self.superadmin)
		response = self.client.get(f"/api/auth/{self.tenant_admin.id}/")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["role"], User.Role.TENANT_ADMIN)

	def test_role_specific_endpoints_enforce_roles(self):
		cases = (
			(self.user, "/api/auth/test/user/", 200),
			(self.user, "/api/auth/test/tenant-admin/", 403),
			(self.tenant_admin, "/api/auth/test/tenant-admin/", 200),
			(self.tenant_admin, "/api/auth/test/super-admin/", 403),
			(self.superadmin, "/api/auth/test/super-admin/", 200),
		)
		for user, url, expected_status in cases:
			with self.subTest(username=user.username, url=url):
				self.client.force_authenticate(user)
				self.assertEqual(self.client.get(url).status_code, expected_status)

	def test_logout_blacklists_refresh_token(self):
		login_response = self.client.post(
			"/api/auth/login/",
			{"username": self.user.username, "password": self.password},
		)
		refresh_token = login_response.data["refresh"]

		logout_response = self.client.post(
			"/api/auth/logout/",
			{"refresh": refresh_token},
			format="json",
		)
		self.assertEqual(logout_response.status_code, 200)

		refresh_response = self.client.post(
			"/api/auth/refresh/",
			{"refresh": refresh_token},
			format="json",
		)
		self.assertEqual(refresh_response.status_code, 401)
