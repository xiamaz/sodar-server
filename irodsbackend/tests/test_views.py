"""Tests for views in the irodsbackend app"""

from irods.test.helpers import make_object
from test_plus.test import TestCase
from unittest import skipIf

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import RequestFactory

# Projectroles dependency
from projectroles.models import Role, OMICS_CONSTANTS
from projectroles.tests.test_models import ProjectMixin, RoleAssignmentMixin
from projectroles.plugins import get_backend_api

# Global constants
PROJECT_ROLE_OWNER = OMICS_CONSTANTS['PROJECT_ROLE_OWNER']
PROJECT_ROLE_DELEGATE = OMICS_CONSTANTS['PROJECT_ROLE_DELEGATE']
PROJECT_ROLE_CONTRIBUTOR = OMICS_CONSTANTS['PROJECT_ROLE_CONTRIBUTOR']
PROJECT_ROLE_GUEST = OMICS_CONSTANTS['PROJECT_ROLE_GUEST']
PROJECT_TYPE_CATEGORY = OMICS_CONSTANTS['PROJECT_TYPE_CATEGORY']
PROJECT_TYPE_PROJECT = OMICS_CONSTANTS['PROJECT_TYPE_PROJECT']

# Local constants
IRODS_TEMP_COLL = 'temp'
IRODS_OBJ_SIZE = 1024
IRODS_OBJ_CONTENT = ''.join('x' for _ in range(IRODS_OBJ_SIZE))
IRODS_OBJ_NAME = 'test1.txt'
IRODS_MD5_NAME = 'test1.txt.md5'
IRODS_NON_PROJECT_PATH = '/' + settings.IRODS_ZONE + \
                         '/home/' + settings.IRODS_USER
IRODS_FAIL_COLL = 'xeiJ1Vie'

IRODS_BACKEND_ENABLED = True if \
    'omics_irods' in settings.ENABLED_BACKEND_PLUGINS else False
IRODS_BACKEND_SKIP_MSG = 'iRODS backend not enabled in settings'


class TestViewsBase(
        TestCase, ProjectMixin, RoleAssignmentMixin):
    """Base class for view testing"""

    def setUp(self):
        self.req_factory = RequestFactory()

        # Get iRODS backend
        self.irods_backend = get_backend_api('omics_irods')
        self.assertIsNotNone(self.irods_backend)

        # Get iRODS session
        self.irods_session = self.irods_backend.get_session()

        # Init roles
        self.role_owner = Role.objects.get_or_create(
            name=PROJECT_ROLE_OWNER)[0]
        self.role_delegate = Role.objects.get_or_create(
            name=PROJECT_ROLE_DELEGATE)[0]
        self.role_contributor = Role.objects.get_or_create(
            name=PROJECT_ROLE_CONTRIBUTOR)[0]
        self.role_guest = Role.objects.get_or_create(
            name=PROJECT_ROLE_GUEST)[0]

        # Init superuser
        self.user = self.make_user('superuser')
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        # Init project with owner
        self.project = self._make_project(
            'TestProject', PROJECT_TYPE_PROJECT, None)
        self.as_owner = self._make_assignment(
            self.project, self.user, self.role_owner)


@skipIf(not IRODS_BACKEND_ENABLED, IRODS_BACKEND_SKIP_MSG)
class TestIrodsStatisticsGetAPIView(TestViewsBase):
    """Tests for the landing zone file statistics API view"""

    def setUp(self):
        super(TestIrodsStatisticsGetAPIView, self).setUp()

        # Build path for test collection
        self.irods_path = self.irods_backend.get_path(
            self.project) + '/' + IRODS_TEMP_COLL

        # Create test collection in iRODS
        self.irods_coll = self.irods_session.collections.create(self.irods_path)

    def test_get_empty_coll(self):
        """Test GET request for stats on an empty collection in iRODS"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'irodsbackend:stats',
                kwargs={
                    'project': self.project.omics_uuid,
                    'path': self.irods_path}))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['file_count'], 0)
            self.assertEqual(response.data['total_size'], 0)

    def test_get_coll_obj(self):
        """Test GET request for stats on a collection with a data object"""

        # Put data object in iRODS
        obj_path = self.irods_path + '/' + IRODS_OBJ_NAME
        data_obj = make_object(
            self.irods_session, obj_path, IRODS_OBJ_CONTENT)

        with self.login(self.user):
            response = self.client.get(reverse(
                'irodsbackend:stats',
                kwargs={
                    'project': self.project.omics_uuid,
                    'path': self.irods_path}))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['file_count'], 1)
            self.assertEqual(response.data['total_size'], IRODS_OBJ_SIZE)

    def test_get_coll_md5(self):
        """Test GET request for stats on a collection with a data object and md5"""

        # Put data object in iRODS
        obj_path = self.irods_path + '/' + IRODS_OBJ_NAME
        data_obj = make_object(
            self.irods_session, obj_path, IRODS_OBJ_CONTENT)

        # Put MD5 data object in iRODS
        md5_path = self.irods_path + '/' + IRODS_MD5_NAME
        md5_obj = make_object(
            self.irods_session, md5_path, IRODS_OBJ_CONTENT)  # Not actual md5

        with self.login(self.user):
            response = self.client.get(reverse(
                'irodsbackend:stats',
                kwargs={
                    'project': self.project.omics_uuid,
                    'path': self.irods_path}))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['file_count'], 1)  # md5 not counted
            self.assertEqual(response.data['total_size'], IRODS_OBJ_SIZE)

    def test_get_coll_not_found(self):
        """Test GET request for stats on a collection which doesn't exist"""
        fail_path = self.irods_path + '/' + IRODS_FAIL_COLL
        self.assertEqual(
            self.irods_session.collections.exists(fail_path), False)

        with self.login(self.user):
            response = self.client.get(reverse(
                'irodsbackend:stats',
                kwargs={
                    'project': self.project.omics_uuid,
                    'path': fail_path}))

            self.assertEqual(response.status_code, 404)

    def test_get_coll_not_in_project(self):
        """Test GET request for stats on a collection not belonging to project"""
        self.assertEqual(
            self.irods_session.collections.exists(IRODS_NON_PROJECT_PATH), True)

        with self.login(self.user):
            response = self.client.get(reverse(
                'irodsbackend:stats',
                kwargs={
                    'project': self.project.omics_uuid,
                    'path': IRODS_NON_PROJECT_PATH}))

            self.assertEqual(response.status_code, 400)