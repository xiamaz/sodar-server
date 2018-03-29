# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-28 08:32
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('adminalerts', '0002_auto_20180105_1538'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminalert',
            name='omics_uuid',
            field=models.UUIDField(default=uuid.uuid4,
                                   help_text='Adminalerts Omics UUID',
                                   null=True),
        ),
    ]