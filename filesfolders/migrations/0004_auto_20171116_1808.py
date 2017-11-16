# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2017-11-16 17:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filesfolders', '0003_auto_20171116_1534'),
    ]

    operations = [
        migrations.AlterField(
            model_name='file',
            name='flag',
            field=models.CharField(blank=True, choices=[('FLAG', 'Flagged'), ('FLAG_HEART', 'Flagged (Heart)'), ('IMPORTANT', 'Important'), ('REVOKED', 'Revoked'), ('SUPERSEDED', 'Superseded')], help_text='Flag (optional)', max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='folder',
            name='flag',
            field=models.CharField(blank=True, choices=[('FLAG', 'Flagged'), ('FLAG_HEART', 'Flagged (Heart)'), ('IMPORTANT', 'Important'), ('REVOKED', 'Revoked'), ('SUPERSEDED', 'Superseded')], help_text='Flag (optional)', max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='hyperlink',
            name='flag',
            field=models.CharField(blank=True, choices=[('FLAG', 'Flagged'), ('FLAG_HEART', 'Flagged (Heart)'), ('IMPORTANT', 'Important'), ('REVOKED', 'Revoked'), ('SUPERSEDED', 'Superseded')], help_text='Flag (optional)', max_length=64, null=True),
        ),
    ]
