from django import template
from django.conf import settings
from django.urls import reverse


from ..models import LandingZone


STATUS_STYLES = {
    'ACTIVE': 'bg-info',
    'PREPARING': 'bg-warning',
    'VALIDATING': 'bg-warning',
    'MOVING': 'bg-warning',
    'MOVED': 'bg-success',
    'FAILED': 'bg-danger'}


register = template.Library()


@register.simple_tag
def get_status_style(zone):
    return STATUS_STYLES[zone.status] \
        if zone.status in STATUS_STYLES else 'bg_faded'


# TODO: Refactor/remove
@register.simple_tag
def get_zone_row_class(zone):
    return 'zone-tr-moved text-muted' if \
        zone.status == 'MOVED' else 'zone-tr-existing'


# TODO: Refactor/remove
@register.simple_tag
def get_irods_cmd(zone):
    """Return iRODS icommand for popover"""
    return '/omicsZone/projects/project{}/landing_zones/{}/{}'.format(
        zone.project.pk, zone.user, zone.title)


@register.simple_tag
def get_details_zones(project, user):
    """Return active user zones for the project details page"""
    return LandingZone.objects.filter(
        project=project, user=user).exclude(status='MOVED').order_by('-pk')


# TODO: Refactor/remove
@register.simple_tag
def get_irods_url(zone):
    return reverse(
        'zone_irods_objects_list',
        kwargs={
            'project': zone.project.pk,
            'zone': zone.pk,
            'path': get_zone_path(zone)})


# TODO: Refactor/remove
@register.simple_tag
def get_zone_path(zone):
    return '/omicsZone/projects/project{}/landing_zones/{}/{}'.format(
        zone.project.pk, zone.user, zone.title)
