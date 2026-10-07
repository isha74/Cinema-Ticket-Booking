from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("movies", "0003_movie_tables_per_cinema_schema"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="movie",
                    name="cinema",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="movies",
                        to="cinema.cinema",
                    ),
                ),
            ],
        ),
    ]
