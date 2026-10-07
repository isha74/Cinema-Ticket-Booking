from rest_framework import serializers

from authentication.models import User

from .models import Screen


class ScreenSerializer(serializers.ModelSerializer):
    cinema = serializers.PrimaryKeyRelatedField(read_only=True)
    cinema_name = serializers.CharField(source="cinema.name", read_only=True)

    class Meta:
        model = Screen
        fields = ("id", "cinema", "cinema_name", "name", "total_seats", "created_at")
        read_only_fields = ("id", "cinema", "cinema_name", "created_at")

    def validate_total_seats(self, total_seats):
        if total_seats < 1:
            raise serializers.ValidationError(
                "A screen must have at least one seat."
            )
        if self.instance is not None and total_seats < self.instance.seats.count():
            raise serializers.ValidationError(
                "Total seats cannot be fewer than the seats already configured."
            )
        return total_seats

    def validate_name(self, name):
        request = self.context.get("request")
        if request is None or request.user.role != User.Role.TENANT_ADMIN:
            return name

        existing_screens = Screen.objects.filter(
            cinema__owner=request.user,
            name=name,
        )
        if self.instance is not None:
            existing_screens = existing_screens.exclude(pk=self.instance.pk)
        if existing_screens.exists():
            raise serializers.ValidationError(
                "A screen with this name already exists for your cinema."
            )
        return name
