# Generated by Django 4.2.18 on 2025-06-02 11:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='high_limit',
        ),
        migrations.RemoveField(
            model_name='order',
            name='low_limit',
        ),
    ]
