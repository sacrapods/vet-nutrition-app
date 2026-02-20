from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intake_form', '0006_vetupload'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomemadeDietQuestionnaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner_name', models.CharField(max_length=200)),
                ('owner_email', models.EmailField(blank=True, max_length=254)),
                ('owner_phone', models.CharField(blank=True, max_length=20)),
                ('pet_name', models.CharField(max_length=100)),
                ('species', models.CharField(choices=[('dog', 'Dog'), ('cat', 'Cat'), ('other', 'Other')], max_length=20)),
                ('breed', models.CharField(blank=True, max_length=100)),
                ('age', models.CharField(blank=True, max_length=100)),
                ('current_weight_kg', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('current_diet_description', models.TextField(blank=True)),
                ('homemade_meals_per_day', models.IntegerField(blank=True, null=True)),
                ('recipe_ingredients', models.TextField(blank=True, help_text='Main ingredients currently fed')),
                ('recipe_preparation', models.TextField(blank=True)),
                ('supplements_medications', models.TextField(blank=True)),
                ('concerns_or_goals', models.TextField(blank=True)),
                ('additional_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
