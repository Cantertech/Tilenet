# Generated by Django 4.2.20 on 2025-05-13 02:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0008_remove_project_subtotal_cost_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectmaterial',
            name='unit',
            field=models.CharField(default='', max_length=50, verbose_name='Unit'),
        ),
    ]
