# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-07 11:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('samplesheets', '0003_auto_20180206_1538'),
    ]

    operations = [
        migrations.AlterField(
            model_name='protocol',
            name='uri',
            field=models.CharField(help_text='Protocol URI', max_length=2048),
        ),
    ]
