import re

from django.db import connection, transaction
from django.utils.text import slugify
from rest_framework import serializers

from authentication.models import User

from .models import Cinema


class TenantAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role")


class CinemaSerializer(serializers.ModelSerializer):
    tenant_admin = TenantAdminSerializer(source="owner", read_only=True)

    class Meta:
        model = Cinema
        fields = (
            "id",
            "name",
            "domain",
            "slug",
            "schema_name",
            "status",
            "address",
            "city",
            "contact_email",
            "contact_phone",
            "tenant_admin",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CinemaUpdateSerializer(serializers.ModelSerializer):
    tenant_admin = TenantAdminSerializer(source="owner", read_only=True)

    class Meta:
        model = Cinema
        fields = (
            "id",
            "name",
            "domain",
            "slug",
            "schema_name",
            "status",
            "address",
            "city",
            "contact_email",
            "contact_phone",
            "tenant_admin",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "domain",
            "slug",
            "schema_name",
            "status",
            "tenant_admin",
            "created_at",
            "updated_at",
        )


class CinemaRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    tenant_admin = TenantAdminSerializer(source="owner", read_only=True)

    class Meta:
        model = Cinema
        fields = (
            "id",
            "username",
            "email",
            "password",
            "name",
            "domain",
            "slug",
            "schema_name",
            "status",
            "address",
            "city",
            "contact_email",
            "contact_phone",
            "tenant_admin",
            "created_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "schema_name",
            "status",
            "tenant_admin",
            "created_at",
        )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_domain(self, value):
        domain = value.strip().lower()
        if not domain:
            raise serializers.ValidationError("Domain is required.")
        if Cinema.objects.filter(domain=domain).exists():
            raise serializers.ValidationError("A cinema with this domain already exists.")
        return domain

    def _build_unique_slug(self, name):
        base_slug = slugify(name) or "cinema"
        slug = base_slug
        counter = 1

        while Cinema.objects.filter(slug=slug).exists():
            counter += 1
            slug = f"{base_slug}-{counter}"

        return slug

    def _build_unique_schema_name(self, domain):
        base_schema = re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_") or "cinema"
        base_schema = base_schema[:63].rstrip("_")
        schema_name = base_schema
        counter = 1

        while Cinema.objects.filter(schema_name=schema_name).exists():
            counter += 1
            suffix = f"_{counter}"
            schema_name = f"{base_schema[:63 - len(suffix)]}{suffix}"

        return schema_name

    def _create_tenant_schema(self, schema_name):
        if connection.vendor != "postgresql":
            return

        quoted_schema_name = connection.ops.quote_name(schema_name)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema_name}")

    @transaction.atomic
    def create(self, validated_data):
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        password = validated_data.pop("password")

        cinema_name = validated_data["name"]
        domain = validated_data["domain"]
        schema_name = self._build_unique_schema_name(domain)

        owner = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.Role.TENANT_ADMIN,
        )

        cinema = Cinema.objects.create(
            **validated_data,
            slug=self._build_unique_slug(cinema_name),
            schema_name=schema_name,
            status=Cinema.Status.PENDING,
            owner=owner,
        )
        self._create_tenant_schema(schema_name)
        return cinema
