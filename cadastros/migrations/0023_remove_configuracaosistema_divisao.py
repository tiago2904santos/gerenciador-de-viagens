from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0022_cargo_area_combustivel_area_unidade_area_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosistema",
            name="divisao",
        ),
    ]
