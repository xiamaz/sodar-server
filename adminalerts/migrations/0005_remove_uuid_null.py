# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-28 08:35
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('adminalerts', '0004_populate_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminalert',
            name='omics_uuid',
            field=models.UUIDField(default=uuid.uuid4,
                                   help_text='Adminalerts Omics UUID',
                                   unique=True),
        ),
    ]