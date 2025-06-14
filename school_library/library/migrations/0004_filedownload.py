# Generated by Django 4.2 on 2025-04-23 11:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0003_reservation_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileDownload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_type', models.CharField(choices=[('book', 'Книга'), ('excerpt', 'Отрывок')], max_length=10, verbose_name='Тип файла')),
                ('downloaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата скачивания')),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='library.book', verbose_name='Книга')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Скачивание файла',
                'verbose_name_plural': 'Скачивания файлов',
                'ordering': ['-downloaded_at'],
            },
        ),
    ]
