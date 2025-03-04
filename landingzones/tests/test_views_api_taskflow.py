"""
Tests for REST API views in the landingzones app with SODAR Taskflow enabled
"""

import json

from django.test import override_settings
from django.urls import reverse

# Projectroles dependency
from projectroles.models import SODAR_CONSTANTS
from projectroles.plugins import get_backend_api

# Samplesheets dependency
from samplesheets.tests.test_io import SampleSheetIOMixin, SHEET_DIR
from landingzones.tests.test_views_api import INVALID_UUID
from samplesheets.tests.test_views_taskflow import SampleSheetTaskflowMixin
from samplesheets.views import RESULTS_COLL, MISC_FILES_COLL, TRACK_HUBS_COLL

# Taskflowbackend dependency
from taskflowbackend.tests.base import TestTaskflowAPIBase

from landingzones.models import LandingZone, DEFAULT_STATUS_INFO
from landingzones.tests.test_models import LandingZoneMixin
from landingzones.tests.test_views_taskflow import (
    LandingZoneTaskflowMixin,
    ZONE_TITLE,
    ZONE_DESC,
    INVALID_REDIS_URL,
)


# Global constants
PROJECT_ROLE_OWNER = SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
PROJECT_ROLE_DELEGATE = SODAR_CONSTANTS['PROJECT_ROLE_DELEGATE']
PROJECT_ROLE_CONTRIBUTOR = SODAR_CONSTANTS['PROJECT_ROLE_CONTRIBUTOR']
PROJECT_ROLE_GUEST = SODAR_CONSTANTS['PROJECT_ROLE_GUEST']
PROJECT_TYPE_CATEGORY = SODAR_CONSTANTS['PROJECT_TYPE_CATEGORY']
PROJECT_TYPE_PROJECT = SODAR_CONSTANTS['PROJECT_TYPE_PROJECT']

# Local constants
SHEET_PATH = SHEET_DIR + 'i_small.zip'
ZONE_STATUS = 'VALIDATING'
ZONE_STATUS_INFO = 'Testing'


class TestLandingZoneAPITaskflowBase(
    SampleSheetIOMixin,
    SampleSheetTaskflowMixin,
    LandingZoneMixin,
    LandingZoneTaskflowMixin,
    TestTaskflowAPIBase,
):
    """Base landing zone API view test class with Taskflow enabled"""

    def setUp(self):
        super().setUp()

        # Get iRODS backend for session access
        self.irods_backend = get_backend_api('omics_irods')
        self.assertIsNotNone(self.irods_backend)
        self.irods = self.irods_backend.get_session()

        # Init project
        # Make project with owner in Taskflow and Django
        self.project, self.owner_as = self.make_project_taskflow(
            title='TestProject',
            type=PROJECT_TYPE_PROJECT,
            parent=self.category,
            owner=self.user,
            description='description',
        )

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Create collections in iRODS
        self.make_irods_colls(self.investigation)


class TestLandingZoneCreateAPIView(TestLandingZoneAPITaskflowBase):
    """Tests for LandingZoneCreateAPIView"""

    def test_post(self):
        """Test LandingZoneCreateAPIView post()"""
        self.assertEqual(LandingZone.objects.count(), 0)

        url = reverse(
            'landingzones:api_create',
            kwargs={'project': self.project.sodar_uuid},
        )
        request_data = {
            'title': 'new zone',
            'assay': str(self.assay.sodar_uuid),
            'description': 'description',
            'user_message': 'user message',
            'configuration': None,
            'config_data': {},
        }
        response = self.request_knox(url, method='POST', data=request_data)

        # Assert status after creation
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LandingZone.objects.count(), 1)
        # Assert status after taskflow has finished
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'ACTIVE')

        # Check result
        # NOTE: date_modified will be changend async, can't test
        response_data = json.loads(response.content)
        expected = {
            'title': zone.title,
            'project': str(self.project.sodar_uuid),
            'user': self.get_serialized_user(self.user),
            'assay': str(self.assay.sodar_uuid),
            'status': 'CREATING',
            'status_info': DEFAULT_STATUS_INFO['CREATING'],
            'status_locked': False,
            'date_modified': response_data['date_modified'],
            'description': zone.description,
            'user_message': zone.user_message,
            'configuration': zone.configuration,
            'config_data': zone.config_data,
            'irods_path': self.irods_backend.get_path(zone),
            'sodar_uuid': str(zone.sodar_uuid),
        }
        self.assertEqual(response_data, expected)

        # Assert collection status
        self.assert_irods_coll(zone)
        self.assert_irods_coll(zone, MISC_FILES_COLL, False)
        self.assert_irods_coll(zone, RESULTS_COLL, False)
        self.assert_irods_coll(zone, TRACK_HUBS_COLL, False)

    def test_post_colls(self):
        """Test LandingZoneCreateAPIView post() with default collections"""
        self.assertEqual(LandingZone.objects.count(), 0)

        url = reverse(
            'landingzones:api_create',
            kwargs={'project': self.project.sodar_uuid},
        )
        request_data = {
            'title': 'new zone',
            'assay': str(self.assay.sodar_uuid),
            'description': 'description',
            'configuration': None,
            'create_colls': True,
            'config_data': {},
        }
        response = self.request_knox(url, method='POST', data=request_data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'ACTIVE')
        self.assert_irods_coll(zone)
        self.assert_irods_coll(zone, MISC_FILES_COLL, True)
        self.assert_irods_coll(zone, RESULTS_COLL, True)
        self.assert_irods_coll(zone, TRACK_HUBS_COLL, True)
        self.assert_irods_coll(zone, '0815-N1-DNA1', False)
        self.assert_irods_coll(zone, '0815-T1-DNA1', False)

    def test_post_colls_plugin(self):
        """Test LandingZoneCreateAPIView post() with plugin collections"""
        self.assertEqual(LandingZone.objects.count(), 0)
        # Mock assay configuration
        self.assay.measurement_type = {'name': 'genome sequencing'}
        self.assay.technology_type = {'name': 'nucleotide sequencing'}
        self.assay.save()
        # Update row cache
        plugin = self.assay.get_plugin()
        self.assertIsNotNone(plugin)
        plugin.update_cache(
            'irods/rows/{}'.format(self.assay.sodar_uuid),
            self.project,
            self.user,
        )

        url = reverse(
            'landingzones:api_create',
            kwargs={'project': self.project.sodar_uuid},
        )
        request_data = {
            'title': 'new zone',
            'assay': str(self.assay.sodar_uuid),
            'description': 'description',
            'configuration': None,
            'create_colls': True,
            'config_data': {},
        }
        response = self.request_knox(url, method='POST', data=request_data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'ACTIVE')
        self.assert_irods_coll(zone)
        self.assert_irods_coll(zone, MISC_FILES_COLL, True)
        self.assert_irods_coll(zone, RESULTS_COLL, True)
        self.assert_irods_coll(zone, TRACK_HUBS_COLL, True)
        self.assert_irods_coll(zone, '0815-N1-DNA1', True)
        self.assert_irods_coll(zone, '0815-T1-DNA1', True)

    # TODO: Test without sodarcache (see issue #1157)

    def test_post_no_investigation(self):
        """Test LandingZoneCreateAPIView post() with no investigation"""
        self.investigation.delete()
        self.assertEqual(LandingZone.objects.count(), 0)

        url = reverse(
            'landingzones:api_create',
            kwargs={'project': self.project.sodar_uuid},
        )
        request_data = {
            'title': 'new zone',
            'assay': str(self.assay.sodar_uuid),
            'description': 'description',
            'configuration': None,
            'config_data': {},
        }
        response = self.request_knox(url, method='POST', data=request_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LandingZone.objects.count(), 0)

    def test_post_no_irods_collections(self):
        """Test LandingZoneCreateAPIView post() with no iRODS collections"""
        self.investigation.irods_status = False
        self.investigation.save()
        self.assertEqual(LandingZone.objects.count(), 0)

        url = reverse(
            'landingzones:api_create',
            kwargs={'project': self.project.sodar_uuid},
        )
        request_data = {
            'title': 'new zone',
            'assay': str(self.assay.sodar_uuid),
            'description': 'description',
            'configuration': None,
            'config_data': {},
        }
        response = self.request_knox(url, method='POST', data=request_data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LandingZone.objects.count(), 0)


class TestLandingZoneSubmitDeleteAPIView(TestLandingZoneAPITaskflowBase):
    """Tests for LandingZoneSubmitDeleteAPIView"""

    def setUp(self):
        super().setUp()
        # Create zone
        self.landing_zone = self.make_landing_zone(
            title=ZONE_TITLE,
            project=self.project,
            user=self.user,
            assay=self.assay,
            description=ZONE_DESC,
            configuration=None,
            config_data={},
        )
        # Create zone in taskflow
        self.make_zone_taskflow(self.landing_zone)

    def test_post(self):
        """Test LandingZoneSubmitDeleteAPIView post()"""
        url = reverse(
            'landingzones:api_submit_delete',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['sodar_uuid'], str(self.landing_zone.sodar_uuid)
        )
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'DELETED')

    def test_post_invalid_status(self):
        """Test post() with invalid zone status (should fail)"""
        self.landing_zone.status = 'MOVED'
        self.landing_zone.save()

        url = reverse(
            'landingzones:api_submit_delete',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LandingZone.objects.count(), 1)
        self.assertEqual(LandingZone.objects.first().status, 'MOVED')

    def test_post_invalid_uuid(self):
        """Test post() with invalid zone UUID (should fail)"""
        url = reverse(
            'landingzones:api_submit_delete',
            kwargs={'landingzone': INVALID_UUID},
        )
        response = self.request_knox(url, method='POST')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(LandingZone.objects.count(), 1)


class TestLandingZoneSubmitMoveAPIView(TestLandingZoneAPITaskflowBase):
    """Tests for TestLandingZoneSubmitMoveAPIView"""

    def setUp(self):
        super().setUp()
        self.landing_zone = self.make_landing_zone(
            title=ZONE_TITLE,
            project=self.project,
            user=self.user,
            assay=self.assay,
            description=ZONE_DESC,
            configuration=None,
            config_data={},
        )
        self.make_zone_taskflow(self.landing_zone)

    def test_post_validate(self):
        """Test post() for validation"""
        self.landing_zone.status = 'FAILED'  # Update to check status change
        self.landing_zone.save()

        url = reverse(
            'landingzones:api_submit_validate',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['sodar_uuid'], str(self.landing_zone.sodar_uuid)
        )
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'ACTIVE')
        self.assertEqual(
            LandingZone.objects.first().status_info,
            'Successfully validated 0 files',
        )

    def test_post_validate_invalid_status(self):
        """Test post() for validation with invalid zone status (should fail)"""
        self.landing_zone.status = 'MOVED'
        self.landing_zone.save()

        url = reverse(
            'landingzones:api_submit_validate',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LandingZone.objects.count(), 1)
        self.assertEqual(LandingZone.objects.first().status, 'MOVED')

    def test_post_move(self):
        """Test post() for moving"""
        url = reverse(
            'landingzones:api_submit_move',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['sodar_uuid'], str(self.landing_zone.sodar_uuid)
        )
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'MOVED')

    def test_post_move_invalid_status(self):
        """Test post() for moving with invalid zone status (should fail)"""
        self.landing_zone.status = 'DELETED'
        self.landing_zone.save()

        url = reverse(
            'landingzones:api_submit_move',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LandingZone.objects.count(), 1)
        self.assertEqual(LandingZone.objects.first().status, 'DELETED')

    @override_settings(REDIS_URL=INVALID_REDIS_URL)
    def test_post_move_lock_failure(self):
        """Test post() for moving with project lock failure"""
        url = reverse(
            'landingzones:api_submit_move',
            kwargs={'landingzone': self.landing_zone.sodar_uuid},
        )
        response = self.request_knox(url, method='POST')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(LandingZone.objects.count(), 1)
        zone = LandingZone.objects.first()
        self.assert_zone_status(zone, 'FAILED')
