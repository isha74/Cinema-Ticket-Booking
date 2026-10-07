from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from cinema.models import Cinema
from cinema.permissions import is_super_admin

from .models import Movie
from .permissions import MovieListCreatePermission, MovieObjectPermission
from .schema import (
    allocate_movie_id,
    cinema_schema,
    ensure_movie_table,
    movie_table_exists,
)
from .serializers import MovieSerializer


def visible_cinemas_for(user, schema_name=None):
    cinemas = Cinema.objects.select_related("owner")
    if is_super_admin(user) or user.role == User.Role.SUPER_ADMIN:
        visible_cinemas = cinemas
    elif user.role == User.Role.TENANT_ADMIN:
        visible_cinemas = cinemas.filter(owner=user)
    elif user.role == User.Role.USER:
        visible_cinemas = cinemas.filter(status=Cinema.Status.ACTIVE)
    else:
        visible_cinemas = cinemas.none()

    if schema_name is None:
        return visible_cinemas

    selected_cinema = visible_cinemas.filter(schema_name=schema_name).first()
    if selected_cinema is None:
        raise PermissionDenied(
            "The X-Schema-Name header does not identify a cinema you can access."
        )
    return visible_cinemas.filter(pk=selected_cinema.pk)


class MovieListCreateView(APIView):
    permission_classes = [MovieListCreatePermission]

    def get(self, request):
        results = []
        schema_name = request.headers.get("X-Schema-Name")
        for cinema in visible_cinemas_for(request.user, schema_name):
            if not movie_table_exists(cinema.schema_name):
                if schema_name is not None:
                    raise APIException(
                        detail=(
                            f"The movies_movie table is missing from schema "
                            f"'{cinema.schema_name}'. Apply the movie schema "
                            "migration or initialize this cinema's movie table."
                        )
                    )
                continue
            with cinema_schema(cinema.schema_name):
                movies = Movie.objects.filter(cinema_id=cinema.pk)
                if (
                    request.user.role == User.Role.USER
                    and not is_super_admin(request.user)
                ):
                    movies = movies.filter(status=Movie.Status.ACTIVE)
                results.extend(MovieSerializer(movies, many=True).data)
        return Response(results)

    def post(self, request):
        schema_name = request.headers.get("X-Schema-Name")
        if not schema_name:
            raise ValidationError(
                {"X-Schema-Name": "This header is required to register a movie."}
            )

        cinema = Cinema.objects.filter(owner=request.user).first()
        if cinema is None or schema_name != cinema.schema_name:
            raise PermissionDenied(
                "The schema in X-Schema-Name is not assigned to your account."
            )

        serializer = MovieSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ensure_movie_table(cinema.schema_name)
        with cinema_schema(cinema.schema_name):
            movie_id = allocate_movie_id()
            save_data = {"cinema": cinema}
            if movie_id:
                save_data["id"] = movie_id
            movie = serializer.save(**save_data)
            data = MovieSerializer(movie, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class MovieDetailView(APIView):
    permission_classes = [MovieObjectPermission]

    def _get_movie_matches(self, pk):
        matches = []
        for cinema in Cinema.objects.all().iterator():
            if not movie_table_exists(cinema.schema_name):
                continue
            with cinema_schema(cinema.schema_name):
                movie = Movie.objects.filter(pk=pk, cinema_id=cinema.pk).first()
                if movie is not None:
                    matches.append((cinema.schema_name, movie.pk))

        if len(matches) > 1:
            return Response(
                {
                    "detail": (
                        "This movie ID exists in multiple cinema schemas. "
                        "Use a cinema-specific route to identify the cinema."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        if not matches:
            raise NotFound("Movie not found.")
        return matches[0]

    def _load_movie(self, schema_name, pk):
        with cinema_schema(schema_name):
            return Movie.objects.select_related("cinema", "cinema__owner").get(pk=pk)

    def get(self, request, pk):
        match = self._get_movie_matches(pk)
        if isinstance(match, Response):
            return match
        schema_name, movie_id = match
        movie = self._load_movie(schema_name, movie_id)
        self.check_object_permissions(request, movie)
        with cinema_schema(schema_name):
            data = MovieSerializer(movie, context={"request": request}).data
        return Response(data)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        match = self._get_movie_matches(pk)
        if isinstance(match, Response):
            return match
        schema_name, movie_id = match
        movie = self._load_movie(schema_name, movie_id)
        self.check_object_permissions(request, movie)
        with cinema_schema(schema_name):
            serializer = MovieSerializer(
                movie,
                data=request.data,
                partial=partial,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            movie = serializer.save()
            data = MovieSerializer(movie, context={"request": request}).data
        return Response(data)

    def delete(self, request, pk):
        match = self._get_movie_matches(pk)
        if isinstance(match, Response):
            return match
        schema_name, movie_id = match
        movie = self._load_movie(schema_name, movie_id)
        self.check_object_permissions(request, movie)
        with cinema_schema(schema_name):
            movie.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
