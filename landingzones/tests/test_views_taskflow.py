"""Integration tests for views in the landingzones Django app with taskflow"""

# NOTE: You must supply 'omics_url': self.live_server_url in taskflow requests!

import hashlib
from irods.test.helpers import make_object
import time
from unittest import skipIf

from django.conf import settings
from django.contrib import auth
from django.core.urlresolvers import reverse

# Projectroles dependency
from projectroles.models import SODAR_CONSTANTS
from projectroles.plugins import get_backend_api
from projectroles.tests.test_views_taskflow import TestTaskflowBase

# Samplesheets dependency
from samplesheets.tests.test_io import SampleSheetIOMixin, SHEET_DIR
from samplesheets.tests.test_views_taskflow import SampleSheetTaskflowMixin

from landingzones.models import LandingZone
from landingzones.tests.test_models import LandingZoneMixin


User = auth.get_user_model()


# Omics constants
PROJECT_ROLE_OWNER = SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
PROJECT_ROLE_DELEGATE = SODAR_CONSTANTS['PROJECT_ROLE_DELEGATE']
PROJECT_ROLE_CONTRIBUTOR = SODAR_CONSTANTS['PROJECT_ROLE_CONTRIBUTOR']
PROJECT_ROLE_GUEST = SODAR_CONSTANTS['PROJECT_ROLE_GUEST']
PROJECT_TYPE_CATEGORY = SODAR_CONSTANTS['PROJECT_TYPE_CATEGORY']
PROJECT_TYPE_PROJECT = SODAR_CONSTANTS['PROJECT_TYPE_PROJECT']
SUBMIT_STATUS_OK = SODAR_CONSTANTS['SUBMIT_STATUS_OK']
SUBMIT_STATUS_PENDING = SODAR_CONSTANTS['SUBMIT_STATUS_PENDING']
SUBMIT_STATUS_PENDING_TASKFLOW = SODAR_CONSTANTS[
    'SUBMIT_STATUS_PENDING_TASKFLOW']


# Local constants
SHEET_PATH = SHEET_DIR + 'i_small.zip'
TASKFLOW_ENABLED = True if \
    'taskflow' in settings.ENABLED_BACKEND_PLUGINS else False
TASKFLOW_SKIP_MSG = 'Taskflow not enabled in settings'

ZONE_TITLE = '20190703_1724'
ZONE_SUFFIX = 'Test Zone'
ZONE_DESC = 'description'
TEST_OBJ_NAME = 'test1.txt'

ASYNC_WAIT_SECONDS = 5
ASYNC_RETRY_COUNT = 3


class LandingZoneTaskflowMixin:
    """Taskflow helpers for landingzones tests"""

    def _make_zone_taskflow(self, zone, request=None):
        """
        Create landing zone in iRODS using omics_taskflow
        :param zone: LandingZone object
        :param request: HTTP request object (optional, default=None)
        :raise taskflow.FlowSubmitException if submit fails
        """
        timeline = get_backend_api('timeline_backend')
        irods_backend = get_backend_api('omics_irods')
        user = request.user if request else zone.user

        self.assertEqual(zone.status, 'CREATING')

        # Create timeline event to prevent taskflow failure
        tl_event = timeline.add_event(
            project=zone.project,
            app_name='landingzones',
            user=user,
            event_name='zone_create',
            description='create landing zone',
            status_type='SUBMIT')

        flow_data = {
            'zone_title': zone.title,
            'zone_uuid': zone.omics_uuid,
            'user_name': user.username,
            'user_uuid': user.omics_uuid,
            'assay_path': irods_backend.get_subdir(
                zone.assay, landing_zone=True),
            'description': zone.description,
            'zone_config': zone.configuration,
            'dirs': []}

        values = {
            'project_uuid': zone.project.omics_uuid,
            'flow_name': 'landing_zone_create',
            'flow_data': flow_data,
            'timeline_uuid': tl_event.omics_uuid,
            'request_mode': 'async',
            'request': request}

        if not request:
            values['omics_url'] = self.live_server_url

        self.taskflow.submit(**values)

        # HACK: Wait for async stuff to finish
        time.sleep(ASYNC_WAIT_SECONDS)
        zone.refresh_from_db()
        self.assertEqual(zone.status, 'ACTIVE')

    def _make_object(self, coll, obj_name, content=None, content_length=1024):
        """
        Create and put a data object into iRODS
        :param coll: iRODSCollection object
        :param obj_name: String
        :param content: Content data (optional)
        :param content_length: Random content length (if content not specified)
        :return: iRODSDataObject object
        """
        if not content:
            content = ''.join('x' for _ in range(content_length))

        obj_path = coll.path + '/' + obj_name
        return make_object(self.irods_session, obj_path, content)

    def _make_md5_object(self, obj):
        """
        Create and put an MD5 checksum object for an existing object in iRODS
        :param obj: iRODSDataObject
        :return: iRODSDataObject
        """
        md5_path = obj.path + '.md5'
        md5_content = ''

        with obj.open() as obj_fp:
            md5_content = hashlib.md5(obj_fp.read()).hexdigest()
        return make_object(self.irods_session, md5_path, md5_content)


class TestLandingZoneCreateView(
        TestTaskflowBase, SampleSheetIOMixin,
        LandingZoneMixin, SampleSheetTaskflowMixin):
    """Tests for the landingzones create view with Taskflow and iRODS"""

    def setUp(self):
        super(TestLandingZoneCreateView, self).setUp()

        # Get iRODS backend for session access
        self.irods_backend = get_backend_api('omics_irods')
        self.assertIsNotNone(self.irods_backend)
        self.irods_session = self.irods_backend.get_session()

        # Init project
        # Make project with owner in Taskflow and Django
        self.project, self.owner_as = self._make_project_taskflow(
            title='TestProject',
            type=PROJECT_TYPE_PROJECT,
            parent=self.category,
            owner=self.user,
            description='description')

        # Import investigation
        self.investigation = self._import_isa_from_file(
            SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Create dirs in iRODS
        self._make_irods_dirs(self.investigation)

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_create_zone(self):
        """Test landingzones creation with taskflow"""

        # Assert precondition
        self.assertEqual(LandingZone.objects.all().count(), 0)

        # Issue POST request
        values = {
            'assay': str(self.assay.omics_uuid),
            'title_suffix': ZONE_SUFFIX,
            'description': ZONE_DESC,
            'configuration': '',
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:create',
                    kwargs={'project': self.project.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response,
                reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.all().count() == 1:
                break

        # Assert zone creation
        self.assertEqual(LandingZone.objects.all().count(), 1)

        # Assert zone status
        zone = LandingZone.objects.first()
        self.assertEqual(zone.status, 'ACTIVE')


class TestLandingZoneMoveView(
        TestTaskflowBase, SampleSheetIOMixin,
        LandingZoneMixin, LandingZoneTaskflowMixin, SampleSheetTaskflowMixin):
    """Tests for the landingzones move/validate view with Taskflow and iRODS"""

    def setUp(self):
        super(TestLandingZoneMoveView, self).setUp()

        # Get iRODS backend for session access
        self.irods_backend = get_backend_api('omics_irods')
        self.assertIsNotNone(self.irods_backend)
        self.irods_session = self.irods_backend.get_session()

        # Init project
        # Make project with owner in Taskflow and Django
        self.project, self.owner_as = self._make_project_taskflow(
            title='TestProject',
            type=PROJECT_TYPE_PROJECT,
            parent=self.category,
            owner=self.user,
            description='description')

        # Import investigation
        self.investigation = self._import_isa_from_file(
            SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Create dirs in iRODS
        self._make_irods_dirs(self.investigation)

        # Create zone
        self.landing_zone = self._make_landing_zone(
            title=ZONE_TITLE,
            project=self.project,
            user=self.user,
            assay=self.assay,
            description=ZONE_DESC,
            configuration=None,
            config_data={})

        # Create zone in taskflow
        self._make_zone_taskflow(self.landing_zone)

        # Get collections
        self.zone_coll = self.irods_session.collections.get(
            self.irods_backend.get_path(self.landing_zone))
        self.assay_coll = self.irods_session.collections.get(
            self.irods_backend.get_path(self.assay))

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_move(self):
        """Test validating and moving a landing zone with objects"""

        # Put files in iRODS
        self.irods_obj = self._make_object(self.zone_coll, TEST_OBJ_NAME)
        self.md5_obj = self._make_md5_object(self.irods_obj)

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'ACTIVE')
        self.assertEqual(len(self.zone_coll.data_objects), 2)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

        # Issue POST request
        values = {
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:move',
                    kwargs={'landingzone': self.landing_zone.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response, reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.first().status == 'MOVED':
                break

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'MOVED')
        self.assertEqual(len(self.zone_coll.data_objects), 0)
        self.assertEqual(len(self.assay_coll.data_objects), 2)

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_move_no_md5(self):
        """Test validating and moving a landing zone without checksum (should fail)"""

        # Put files in iRODS
        self.irods_obj = self._make_object(self.zone_coll, TEST_OBJ_NAME)
        # No md5

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'ACTIVE')
        self.assertEqual(len(self.zone_coll.data_objects), 1)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

        # Issue POST request
        values = {
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:move',
                    kwargs={'landingzone': self.landing_zone.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response, reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.first().status == 'FAILED':
                break

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'FAILED')
        self.assertEqual(len(self.zone_coll.data_objects), 1)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_validate(self):
        """Test validating a landing zone with objects without moving"""

        # Put files in iRODS
        self.irods_obj = self._make_object(self.zone_coll, TEST_OBJ_NAME)
        self.md5_obj = self._make_md5_object(self.irods_obj)

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'ACTIVE')
        self.assertEqual(len(self.zone_coll.data_objects), 2)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

        # Issue POST request
        values = {
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:validate',
                    kwargs={'landingzone': self.landing_zone.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response, reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.first().status == 'ACTIVE':
                break

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'ACTIVE')
        self.assertEqual(len(self.zone_coll.data_objects), 2)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_validate_no_md5(self):
        """Test validating a landing zone without checksum (should fail)"""

        # Put files in iRODS
        self.irods_obj = self._make_object(self.zone_coll, TEST_OBJ_NAME)
        # No md5

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'ACTIVE')
        self.assertEqual(len(self.zone_coll.data_objects), 1)
        self.assertEqual(len(self.assay_coll.data_objects), 0)

        # Issue POST request
        values = {
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:validate',
                    kwargs={'landingzone': self.landing_zone.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response, reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.first().status == 'FAILED':
                break

        # Assert preconditions
        self.assertEqual(LandingZone.objects.first().status, 'FAILED')
        self.assertEqual(len(self.zone_coll.data_objects), 1)
        self.assertEqual(len(self.assay_coll.data_objects), 0)


class TestLandingZoneDeleteView(
        TestTaskflowBase, SampleSheetIOMixin,
        LandingZoneMixin, LandingZoneTaskflowMixin, SampleSheetTaskflowMixin):
    """Tests for the landingzones delete view with Taskflow and iRODS"""

    def setUp(self):
        super(TestLandingZoneDeleteView, self).setUp()

        # Init project
        # Make project with owner in Taskflow and Django
        self.project, self.owner_as = self._make_project_taskflow(
            title='TestProject',
            type=PROJECT_TYPE_PROJECT,
            parent=self.category,
            owner=self.user,
            description='description')

        # Import investigation
        self.investigation = self._import_isa_from_file(
            SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Create dirs in iRODS
        self._make_irods_dirs(self.investigation)

        # Create zone
        self.landing_zone = self._make_landing_zone(
            title=ZONE_TITLE,
            project=self.project,
            user=self.user,
            assay=self.assay,
            description=ZONE_DESC,
            configuration=None,
            config_data={})

        # Create zone in taskflow
        self._make_zone_taskflow(self.landing_zone)

    @skipIf(not TASKFLOW_ENABLED, TASKFLOW_SKIP_MSG)
    def test_delete_zone(self):
        """Test landingzones deletion with taskflow"""

        # Assert precondition
        self.assertEqual(LandingZone.objects.all().count(), 1)

        # Issue POST request
        values = {
            'omics_url': self.live_server_url}

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'landingzones:delete',
                    kwargs={'landingzone': self.landing_zone.omics_uuid}),
                values)

        # Assert redirect
        with self.login(self.user):
            self.assertRedirects(
                response, reverse(
                    'landingzones:list',
                    kwargs={'project': self.project.omics_uuid}))

        # HACK: Wait for async stuff to finish
        for i in range(0, ASYNC_RETRY_COUNT):
            time.sleep(ASYNC_WAIT_SECONDS)

            if LandingZone.objects.first().status == 'DELETED':
                break

        # Assert zone deletion
        self.assertEqual(LandingZone.objects.all().count(), 1)
        self.assertEqual(LandingZone.objects.first().status, 'DELETED')
