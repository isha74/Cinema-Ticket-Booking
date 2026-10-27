from decimal import Decimal

from rest_framework import serializers

from movies.models import Movie

from .models import Screen, Seat, Show, ShowSeatPrice


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
        if (
            self.instance is not None
            and self.instance.seats.exists()
            and total_seats != self.instance.total_seats
        ):
            raise serializers.ValidationError(
                "Screen capacity cannot change after its permanent layout is configured."
            )
        if self.instance is not None and total_seats < self.instance.seats.count():
            raise serializers.ValidationError(
                "Total seats cannot be fewer than the seats already configured."
            )
        return total_seats

    def validate_name(self, name):
        request = self.context.get("request")
        if request is None:
            return name
        existing_screens = Screen.objects.filter(
            cinema_id=self.context["cinema"].pk,
            name=name,
        )
        if self.instance is not None:
            existing_screens = existing_screens.exclude(pk=self.instance.pk)
        if existing_screens.exists():
            raise serializers.ValidationError(
                "A screen with this name already exists for your cinema."
            )
        return name


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ("id", "screen", "row", "seat_number", "position", "seat_type")
        read_only_fields = fields


class LayoutRowSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=10, trim_whitespace=True)
    seat_count = serializers.IntegerField(min_value=1)
    seat_type = serializers.ChoiceField(choices=Seat.SeatType.choices)
    gaps_after = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        gaps_after = attrs["gaps_after"]
        if len(gaps_after) != len(set(gaps_after)):
            raise serializers.ValidationError(
                {"gaps_after": "Gap positions must be unique."}
            )
        if any(position >= attrs["seat_count"] for position in gaps_after):
            raise serializers.ValidationError(
                {"gaps_after": "Each gap must be after a seat, not after the last seat."}
            )
        if attrs["seat_count"] + len(gaps_after) > 32767:
            raise serializers.ValidationError(
                {"gaps_after": "The row's seat positions exceed the supported limit."}
            )
        return attrs


class ScreenLayoutSerializer(serializers.Serializer):
    rows = LayoutRowSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        rows = attrs["rows"]
        labels = [row["label"].casefold() for row in rows]
        if len(labels) != len(set(labels)):
            raise serializers.ValidationError(
                {"rows": "Row labels must be unique."}
            )
        seat_numbers = [
            f"{row['label']}{number}"
            for row in rows
            for number in range(1, row["seat_count"] + 1)
        ]
        if any(len(number) > 10 for number in seat_numbers):
            raise serializers.ValidationError(
                {"rows": "Generated seat numbers cannot exceed 10 characters."}
            )
        if len(seat_numbers) != len(set(seat_numbers)):
            raise serializers.ValidationError(
                {"rows": "The layout would generate duplicate seat numbers."}
            )

        screen = self.context["screen"]
        generated_count = sum(row["seat_count"] for row in rows)
        if generated_count != screen.total_seats:
            raise serializers.ValidationError(
                {
                    "rows": (
                        f"The layout defines {generated_count} seats, but this screen "
                        f"has a capacity of {screen.total_seats}."
                    )
                }
            )
        return attrs


class ShowSerializer(serializers.ModelSerializer):
    movie = serializers.PrimaryKeyRelatedField(queryset=Movie.objects.all())
    screen = serializers.PrimaryKeyRelatedField(queryset=Screen.objects.all())
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    screen_name = serializers.CharField(source="screen.name", read_only=True)

    class Meta:
        model = Show
        fields = (
            "id",
            "movie",
            "movie_title",
            "screen",
            "screen_name",
            "show_date",
            "start_time",
            "end_time",
            "created_at",
        )
        read_only_fields = ("id", "movie_title", "screen_name", "created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cinema = self.context.get("cinema")
        if cinema is not None:
            self.fields["movie"].queryset = Movie.objects.filter(
                cinema_id=cinema.pk
            )
            self.fields["screen"].queryset = Screen.objects.filter(
                cinema_id=cinema.pk
            )

    def validate(self, attrs):
        cinema = self.context["cinema"]
        movie = attrs.get("movie", self.instance.movie if self.instance else None)
        screen = attrs.get("screen", self.instance.screen if self.instance else None)
        show_date = attrs.get(
            "show_date",
            self.instance.show_date if self.instance else None,
        )
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )
        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        if movie is not None and movie.cinema_id != cinema.pk:
            raise serializers.ValidationError(
                {"movie": "Select a movie belonging to your cinema."}
            )
        if screen is not None and screen.cinema_id != cinema.pk:
            raise serializers.ValidationError(
                {"screen": "Select a screen belonging to your cinema."}
            )
        if screen is not None and not screen.seats.exists():
            raise serializers.ValidationError(
                {"screen": "Configure the screen's permanent seat layout first."}
            )

        if start_time is not None and end_time is not None and end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "The show end time must be later than the start time."}
            )

        if screen is not None and show_date is not None:
            if start_time is not None and end_time is not None:
                overlapping = Show.objects.filter(
                    screen=screen,
                    show_date=show_date,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                if self.instance is not None:
                    overlapping = overlapping.exclude(pk=self.instance.pk)
                if overlapping.exists():
                    raise serializers.ValidationError(
                        {"start_time": "This show overlaps another show on this screen."}
                    )
        return attrs


class ShowSeatPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowSeatPrice
        fields = ("id", "show", "seat_type", "price")
        read_only_fields = ("id", "show")

    def validate_price(self, price):
        if price <= Decimal("0"):
            raise serializers.ValidationError("Price must be greater than zero.")
        return price


class ShowPriceConfigurationSerializer(serializers.Serializer):
    prices = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate(self, attrs):
        price_serializer = ShowSeatPriceSerializer(
            data=[
                {"seat_type": item.get("seat_type"), "price": item.get("price")}
                for item in attrs["prices"]
            ],
            many=True,
        )
        price_serializer.is_valid(raise_exception=True)
        prices = price_serializer.validated_data
        types = [item["seat_type"] for item in prices]
        if len(types) != len(set(types)):
            raise serializers.ValidationError(
                {"prices": "Each seat type can have only one price per show."}
            )
        show = self.context["show"]
        seat_types = set(
            show.screen.seats.values_list("seat_type", flat=True).distinct()
        )
        if set(types) != seat_types:
            raise serializers.ValidationError(
                {
                    "prices": (
                        "Provide exactly one price for each seat type used by this screen."
                    )
                }
            )
        return {"prices": prices}


class ShowSeatListSerializer(SeatSerializer):
    price = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta(SeatSerializer.Meta):
        fields = SeatSerializer.Meta.fields + ("price", "status", "is_available")

    def get_price(self, seat):
        prices = self.context["show_prices"]
        return prices.get(seat.seat_type)

    def get_is_available(self, seat):
        return self.context["seat_statuses"].get(seat.pk, "AVAILABLE") == "AVAILABLE"

    def get_status(self, seat):
        return self.context["seat_statuses"].get(seat.pk, "AVAILABLE")


class CustomerShowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cinema_slug = serializers.CharField(source="screen.cinema.slug")
    cinema_name = serializers.CharField(source="screen.cinema.name")
    city = serializers.CharField(source="screen.cinema.city")
    movie_id = serializers.IntegerField(source="movie.id")
    movie_title = serializers.CharField(source="movie.title")
    movie_poster = serializers.ImageField(source="movie.poster", allow_null=True)
    description = serializers.CharField(source="movie.description")
    duration = serializers.IntegerField(source="movie.duration")
    language = serializers.CharField(source="movie.language")
    genre = serializers.CharField(source="movie.genre")
    release_date = serializers.DateField(source="movie.release_date")
    screen_id = serializers.IntegerField(source="screen.id")
    screen_name = serializers.CharField(source="screen.name")
    show_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    seats_available = serializers.IntegerField()
    prices = serializers.DictField()
