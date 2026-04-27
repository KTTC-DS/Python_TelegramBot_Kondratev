from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='status',
            field=models.CharField(choices=[('scheduled', 'Запланировано'), ('pending', 'Ожидание подтверждения'), ('cancelled', 'Отменено'), ('completed', 'Завершено'), ('confirmed', 'Подтверждено')], default='pending', max_length=40),
        ),
    ]