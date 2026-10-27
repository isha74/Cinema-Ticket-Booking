from rest_framework import serializers

from .models import Booking, BookingSeat


class BookingCreateSerializer(serializers.Serializer):
    cinema_slug = serializers.SlugField(max_length=255)
    show = serializers.IntegerField(min_value=1)
    seats = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_seats(self, seats):
        if len(seats) != len(set(seats)):
            raise serializers.ValidationError("Seat IDs must be unique.")
        return seats


class BookingSeatSerializer(serializers.ModelSerializer):
    seat_number = serializers.CharField(source="seat.seat_number", read_only=True)
    seat_type = serializers.CharField(source="seat.seat_type", read_only=True)

    class Meta:
        model = BookingSeat
        fields = ("seat", "seat_number", "seat_type", "price_at_booking")


class BookingSerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source="show.movie.title", read_only=True)
    movie_poster = serializers.ImageField(
        source="show.movie.poster",
        read_only=True,
    )
    show_date = serializers.DateField(source="show.show_date", read_only=True)
    start_time = serializers.TimeField(source="show.start_time", read_only=True)
    end_time = serializers.TimeField(source="show.end_time", read_only=True)
    screen_name = serializers.CharField(source="show.screen.name", read_only=True)
    cinema = serializers.CharField(source="show.screen.cinema.name", read_only=True)
    cinema_slug = serializers.SlugField(
        source="show.screen.cinema.slug",
        read_only=True,
    )
    seats = BookingSeatSerializer(source="booking_seats", many=True, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "booking_reference",
            "cinema",
            "cinema_slug",
            "movie_title",
            "movie_poster",
            "show",
            "show_date",
            "start_time",
            "end_time",
            "screen_name",
            "seats",
            "total_amount",
            "status",
            "hold_expires_at",
            "created_at",
        )
        read_only_fields = fields
