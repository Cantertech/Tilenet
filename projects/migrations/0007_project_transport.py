# Generated by Django 4.2.20 on 2025-05-03 05:13

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_project_total_floor_area_project_total_wall_area'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='transport',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Transport'),
        ),
    ]
