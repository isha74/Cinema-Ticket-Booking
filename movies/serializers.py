from rest_framework import serializers

from .models import Movie


class MovieSerializer(serializers.ModelSerializer):
    cinema = serializers.PrimaryKeyRelatedField(read_only=True)
    cinema_name = serializers.CharField(source="cinema.name", read_only=True)
    duration = serializers.IntegerField(min_value=1, max_value=32767)

    class Meta:
        model = Movie
        fields = (
            "id",
            "cinema",
            "cinema_name",
            "title",
            "description",
            "duration",
            "language",
            "genre",
            "release_date",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "cinema", "cinema_name", "created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.method == "POST":
            self.fields["status"].read_only = True
