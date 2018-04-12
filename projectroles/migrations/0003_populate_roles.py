# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-11 16:00
from __future__ import unicode_literals

from django.db import migrations


def populate_roles(apps, schema_editor):
    Role = apps.get_model('projectroles', 'Role')

    def save_role(name, description):
        role = Role(name=name, description=description)
        role.save()

    # Owner
    save_role(
        'project owner',
        'The project owner has full access to project data; rights to add, '
        'modify and remove project members; right to assign a project '
        'delegate. Each project must have exactly one owner.')

    # Delegate
    save_role(
        'project delegate',
        'The project delegate has all the rights of a project owner with the '
        'exception of assigning a delegate. A maximum of one delegate can be '
        'set per project. A delegate role can be set by project owner.')

    # Contributor
    save_role(
        'project contributor',
        'A project member with ability to view and add project data. Can edit '
        'their own data.')

    # Guest
    save_role(
        'project guest',
        'Read-only access to a project. Can view data in project, can not add '
        'or edit.')


class Migration(migrations.Migration):

    dependencies = [
        ('projectroles', '0002_auto_20180411_1758'),
    ]

    operations = [
        migrations.RunPython(populate_roles),
    ]