"""Tests for views in the filesfolders app"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import RequestFactory

from test_plus.test import TestCase

# Projectroles dependency
from projectroles.models import Role, OMICS_CONSTANTS
from projectroles.tests.test_models import ProjectMixin, RoleAssignmentMixin
from projectroles.project_settings import set_project_setting

from ..models import File, Folder, HyperLink
from .test_models import FolderMixin, FileMixin, HyperLinkMixin
from ..utils import build_public_url


# Global constants from settings
PROJECT_ROLE_OWNER = OMICS_CONSTANTS['PROJECT_ROLE_OWNER']
PROJECT_ROLE_DELEGATE = OMICS_CONSTANTS['PROJECT_ROLE_DELEGATE']
PROJECT_ROLE_CONTRIBUTOR = OMICS_CONSTANTS['PROJECT_ROLE_CONTRIBUTOR']
PROJECT_ROLE_GUEST = OMICS_CONSTANTS['PROJECT_ROLE_GUEST']
PROJECT_ROLE_STAFF = OMICS_CONSTANTS['PROJECT_ROLE_STAFF']
PROJECT_TYPE_CATEGORY = OMICS_CONSTANTS['PROJECT_TYPE_CATEGORY']
PROJECT_TYPE_PROJECT = OMICS_CONSTANTS['PROJECT_TYPE_PROJECT']

# Local constants
APP_NAME = 'filesfolders'
SECRET = '7dqq83clo2iyhg29hifbor56og6911r5'


class TestViewsBase(
        TestCase, ProjectMixin, RoleAssignmentMixin, FileMixin, FolderMixin,
        HyperLinkMixin):
    """Base class for view testing"""

    def setUp(self):
        self.req_factory = RequestFactory()

        # Init roles
        self.role_owner = Role.objects.get_or_create(
            name=PROJECT_ROLE_OWNER)[0]
        self.role_delegate = Role.objects.get_or_create(
            name=PROJECT_ROLE_DELEGATE)[0]
        self.role_staff = Role.objects.get_or_create(
            name=PROJECT_ROLE_STAFF)[0]
        self.role_contributor = Role.objects.get_or_create(
            name=PROJECT_ROLE_CONTRIBUTOR)[0]
        self.role_guest = Role.objects.get_or_create(
            name=PROJECT_ROLE_GUEST)[0]

        # Init superuser
        self.user = self.make_user('superuser')
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        # Init project and owner role
        self.project = self._make_project(
            'TestProject', PROJECT_TYPE_PROJECT, None)
        self.owner_as = self._make_assignment(
            self.project, self.user, self.role_owner)

        # Change public link setting from default
        set_project_setting(
            self.project, APP_NAME, 'allow_public_links', True)

        # Init file content
        self.file_content = bytes('content'.encode('utf-8'))
        self.file_content_alt = bytes('alt content'.encode('utf-8'))

        # Init file
        self.file = self._make_file(
            name='file.txt',
            file_name='file.txt',
            file_content=self.file_content,
            project=self.project,
            folder=None,
            owner=self.user,
            description='',
            public_url=True,
            secret=SECRET)

        # Init folder
        self.folder = self._make_folder(
            name='folder',
            project=self.project,
            folder=None,
            owner=self.user,
            description='')

        # Init link
        self.hyperlink = self._make_hyperlink(
            name='Link',
            url='http://www.google.com/',
            project=self.project,
            folder=None,
            owner=self.user,
            description='')


# List View --------------------------------------------------------------


class TestListView(TestViewsBase):
    """Tests for the file list view"""

    def test_render(self):
        """Test rendering of the project root view"""
        with self.login(self.user):
            response = self.client.get(
                reverse('project_files', kwargs={'project': self.project.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.project.pk)
            self.assertIsNotNone(response.context['folders'])
            self.assertIsNotNone(response.context['files'])
            self.assertIsNotNone(response.context['links'])

    def test_render_in_folder(self):
        """Test rendering of a folder view within the project"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'project_files',
                kwargs={'project': self.project.pk, 'folder': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.project.pk)
            self.assertIsNotNone(response.context['folder_breadcrumb'])
            self.assertIsNotNone(response.context['files'])
            self.assertIsNotNone(response.context['links'])


# File Views -------------------------------------------------------------


class TestFileCreateView(TestViewsBase):
    """Tests for the File create view"""

    def test_render(self):
        """Test rendering of the File create view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_create', kwargs={'project': self.project.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)

    def test_render_in_folder(self):
        """Test rendering of the File create view under a folder"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_create', kwargs={
                    'project': self.project.pk,
                    'folder': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)
            self.assertEqual(response.context['folder'].pk, self.folder.pk)

    def test_create(self):
        """Test file creation"""

        self.assertEqual(File.objects.all().count(), 1)

        post_data = {
            'name': 'new_file.txt',
            'file': SimpleUploadedFile('new_file.txt', self.file_content),
            'folder': '',
            'description': '',
            'flag': '',
            'public_url': False}

        with self.login(self.user):
            response = self.client.post(
                reverse('file_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={'project': self.project.pk}))

        self.assertEqual(File.objects.all().count(), 2)

    def test_create_in_folder(self):
        """Test file creation within a folder"""
        self.assertEqual(File.objects.all().count(), 1)

        post_data = {
            'name': 'new_file.txt',
            'file': SimpleUploadedFile('new_file.txt', self.file_content),
            'folder': self.folder.pk,
            'description': '',
            'flag': '',
            'public_url': False}

        with self.login(self.user):
            response = self.client.post(
                reverse('file_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={
                    'project': self.project.pk, 'folder': self.folder.pk}))

        self.assertEqual(File.objects.all().count(), 2)

    def test_create_existing(self):
        """Test file create with an existing file name (should fail)"""
        self.assertEqual(File.objects.all().count(), 1)

        post_data = {
            'name': 'file.txt',
            'file': SimpleUploadedFile('file.txt', self.file_content_alt),
            'folder': '',
            'description': '',
            'flag': '',
            'public_url': False}

        with self.login(self.user):
            response = self.client.post(
                reverse('file_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

        self.assertEqual(File.objects.all().count(), 1)


class TestFileUpdateView(TestViewsBase):
    """Tests for the File update view"""

    def test_render(self):
        """Test rendering of the File update view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_update', kwargs={
                    'project': self.project.pk,
                    'pk': self.file.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.file.pk)

    def test_update(self):
        """Test file update with different content"""
        self.assertEqual(File.objects.all().count(), 1)
        self.assertEqual(self.file.file.read(), self.file_content)

        post_data = {
            'name': 'file.txt',
            'file': SimpleUploadedFile('file.txt', self.file_content_alt),
            'folder': '',
            'description': '',
            'flag': '',
            'public_url': False}

        with self.login(self.user):
            response = self.client.post(
                reverse('file_update', kwargs={
                    'project': self.project.pk, 'pk': self.file.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={'project': self.project.pk}))

        self.assertEqual(File.objects.all().count(), 1)
        self.file.refresh_from_db()
        self.assertEqual(self.file.file.read(), self.file_content_alt)

    def test_update_existing(self):
        """Test file update with a file name that already exists (should fail)"""

        new_file = self._make_file(
            name='file2.txt',
            file_name='file2.txt',
            file_content=self.file_content,
            project=self.project,
            folder=None,
            owner=self.user,
            description='',
            public_url=True,
            secret='abc123')

        self.assertEqual(File.objects.all().count(), 2)

        post_data = {
            'name': 'file2.txt',
            'file': SimpleUploadedFile('file2.txt', self.file_content_alt),
            'folder': '',
            'description': '',
            'flag': '',
            'public_url': False}

        with self.login(self.user):
            response = self.client.post(
                reverse('file_update', kwargs={
                    'project': self.project.pk, 'pk': self.file.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

        self.assertEqual(File.objects.all().count(), 2)
        self.file.refresh_from_db()
        self.assertEqual(self.file.file.read(), self.file_content)


class TestFileDeleteView(TestViewsBase):
    """Tests for the File delete view"""

    def test_render(self):
        """Test rendering of the File delete view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_delete', kwargs={
                    'project': self.project.pk,
                    'pk': self.file.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.file.pk)


class TestFileServeView(TestViewsBase):
    """Tests for the File serving view"""

    def test_render(self):
        """Test rendering of the File serving view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_serve', kwargs={
                    'pk': self.file.pk,
                    'project': self.project.pk,
                    'file_name': self.file.name}))
            self.assertEqual(response.status_code, 200)


class TestFileServePublicView(TestViewsBase):
    """Tests for the File public serving view"""

    def test_render(self):
        """Test rendering of the File public serving view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_serve_public', kwargs={
                    'secret': SECRET,
                    'file_name': self.file.name}))
            self.assertEqual(response.status_code, 200)

    def test_bad_request_setting(self):
        """Test bad request response from the public serving view if public
        linking is disabled via settings"""
        set_project_setting(
            self.project, APP_NAME, 'allow_public_links', False)

        with self.login(self.user):
            response = self.client.get(reverse(
                'file_serve_public', kwargs={
                    'secret': SECRET,
                    'file_name': self.file.name}))
            self.assertEqual(response.status_code, 400)

    def test_bad_request_file_flag(self):
        """Test bad request response from the public serving view if the file
        can not be served publicly"""
        self.file.public_url = False
        self.file.save()

        with self.login(self.user):
            response = self.client.get(reverse(
                'file_serve_public', kwargs={
                    'secret': SECRET,
                    'file_name': self.file.name}))
            self.assertEqual(response.status_code, 400)

    def test_bad_request_no_file(self):
        """Test bad request response from the public serving view if the file
        has been deleted"""

        file_name = self.file.name
        self.file.delete()

        with self.login(self.user):
            response = self.client.get(reverse(
                'file_serve_public', kwargs={
                    'secret': SECRET,
                    'file_name': file_name}))
            self.assertEqual(response.status_code, 400)


class TestFilePublicLinkView(TestViewsBase):
    """Tests for the File public link view"""

    def test_render(self):
        """Test rendering of the File public link view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'file_public_link', kwargs={
                    'pk': self.file.pk,
                    'project': self.project.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context['public_url'], build_public_url(
                    self.file,
                    self.req_factory.get(
                        'file_public_link',
                        kwargs={
                            'pk': self.file.pk,
                            'project': self.project.pk})))

    def test_redirect_setting(self):
        """Test redirecting from the public link view if public linking is
        disabled via settings """
        set_project_setting(
            self.project, APP_NAME, 'allow_public_links', False)

        with self.login(self.user):
            response = self.client.get(reverse(
                'file_public_link', kwargs={
                    'pk': self.file.pk,
                    'project': self.project.pk}))
            self.assertEqual(response.status_code, 302)

    def test_redirect_no_file(self):
        """Test redirecting from the public link view if the file has been
        deleted"""
        file_pk = self.file.pk
        self.file.delete()

        with self.login(self.user):
            response = self.client.get(reverse(
                'file_public_link', kwargs={
                    'pk': file_pk,
                    'project': self.project.pk}))
            self.assertEqual(response.status_code, 302)


# Folder Views -----------------------------------------------------------


class TestFolderCreateView(TestViewsBase):
    """Tests for the File create view"""

    def test_render(self):
        """Test rendering of the Folder create view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'folder_create', kwargs={'project': self.project.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)

    def test_render_in_folder(self):
        """Test rendering of the Folder create view under a folder"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'folder_create', kwargs={
                    'project': self.project.pk,
                    'folder': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)
            self.assertEqual(response.context['folder'].pk, self.folder.pk)

    def test_create(self):
        """Test folder creation"""
        self.assertEqual(Folder.objects.all().count(), 1)

        post_data = {
            'name': 'new_folder',
            'folder': '',
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('folder_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={
                    'project': self.project.pk}))

        self.assertEqual(Folder.objects.all().count(), 2)

    def test_create_in_folder(self):
        """Test folder creation within a folder"""
        self.assertEqual(Folder.objects.all().count(), 1)

        post_data = {
            'name': 'new_folder',
            'folder': self.folder.pk,
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('folder_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={
                    'project': self.project.pk,
                    'folder': self.folder.pk}))

        self.assertEqual(Folder.objects.all().count(), 2)


class TestFolderUpdateView(TestViewsBase):
    """Tests for the Folder update view"""

    def test_render(self):
        """Test rendering of the Folder update view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'folder_update', kwargs={
                    'pk': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.folder.pk)

    def test_update(self):
        """Test folder update"""
        self.assertEqual(Folder.objects.all().count(), 1)

        post_data = {
            'name': 'renamed_folder',
            'folder': '',
            'description': 'updated description',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('folder_update', kwargs={
                    'pk': self.folder.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={'project': self.project.pk}))

        self.assertEqual(Folder.objects.all().count(), 1)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.name, 'renamed_folder')
        self.assertEqual(self.folder.description, 'updated description')

    def test_update_existing(self):
        """Test folder update with a name that already exists (should fail)"""

        self._make_folder(
            name='folder2',
            project=self.project,
            folder=None,
            owner=self.user,
            description='')

        self.assertEqual(Folder.objects.all().count(), 2)

        post_data = {
            'name': 'folder2',
            'folder': '',
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('folder_update', kwargs={
                    'pk': self.folder.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

        self.assertEqual(Folder.objects.all().count(), 2)
        self.folder.refresh_from_db()
        self.assertEqual(self.folder.name, 'folder')


class TestFolderDeleteView(TestViewsBase):
    """Tests for the File delete view"""

    def test_render(self):
        """Test rendering of the Folder delete view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'folder_delete', kwargs={
                    'pk': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.folder.pk)


# HyperLink Views --------------------------------------------------------


class TestHyperLinkCreateView(TestViewsBase):
    """Tests for the HyperLink create view"""

    def test_render(self):
        """Test rendering of the HyperLink create view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'hyperlink_create', kwargs={'project': self.project.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)

    def test_render_in_folder(self):
        """Test rendering of the HyperLink create view under a folder"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'hyperlink_create', kwargs={
                    'project': self.project.pk,
                    'folder': self.folder.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['project'].pk, self.project.pk)
            self.assertEqual(response.context['folder'].pk, self.folder.pk)

    def test_create(self):
        """Test hyperlink creation"""
        self.assertEqual(HyperLink.objects.all().count(), 1)

        post_data = {
            'name': 'new link',
            'url': 'http://link.com',
            'folder': '',
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('hyperlink_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={
                    'project': self.project.pk}))

        self.assertEqual(HyperLink.objects.all().count(), 2)

    def test_create_in_folder(self):
        """Test folder creation within a folder"""
        self.assertEqual(HyperLink.objects.all().count(), 1)

        post_data = {
            'name': 'new link',
            'url': 'http://link.com',
            'folder': self.folder.pk,
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('hyperlink_create', kwargs={
                    'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={
                    'project': self.project.pk,
                    'folder': self.folder.pk}))

        self.assertEqual(HyperLink.objects.all().count(), 2)


class TestHyperLinkUpdateView(TestViewsBase):
    """Tests for the HyperLink update view"""

    def test_render(self):
        """Test rendering of the HyperLink update view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'hyperlink_update', kwargs={
                    'project': self.project.pk,
                    'pk': self.hyperlink.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.hyperlink.pk)

    def test_update(self):
        """Test hyperlink update"""
        self.assertEqual(HyperLink.objects.all().count(), 1)

        post_data = {
            'name': 'Renamed Link',
            'url': 'http://updated.com',
            'folder': '',
            'description': 'updated description',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('hyperlink_update', kwargs={
                    'project': self.project.pk,
                    'pk': self.hyperlink.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse(
                'project_files', kwargs={'project': self.project.pk}))

        self.assertEqual(HyperLink.objects.all().count(), 1)
        self.hyperlink.refresh_from_db()
        self.assertEqual(self.hyperlink.name, 'Renamed Link')
        self.assertEqual(self.hyperlink.url, 'http://updated.com')
        self.assertEqual(self.hyperlink.description, 'updated description')

    def test_update_existing(self):
        """Test hyperlink update with a name that already exists (should fail)"""

        self._make_hyperlink(
            name='Link2',
            url='http://url2.com',
            project=self.project,
            folder=None,
            owner=self.user,
            description='')

        self.assertEqual(HyperLink.objects.all().count(), 2)

        post_data = {
            'name': 'Link2',
            'url': self.hyperlink.url,
            'folder': '',
            'description': '',
            'flag': ''}

        with self.login(self.user):
            response = self.client.post(
                reverse('hyperlink_update', kwargs={
                    'project': self.project.pk,
                    'pk': self.hyperlink.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

        self.assertEqual(HyperLink.objects.all().count(), 2)
        self.hyperlink.refresh_from_db()
        self.assertEqual(self.hyperlink.name, 'Link')


class TestHyperLinkDeleteView(TestViewsBase):
    """Tests for the HyperLink delete view"""

    def test_render(self):
        """Test rendering of the File delete view"""
        with self.login(self.user):
            response = self.client.get(reverse(
                'hyperlink_delete', kwargs={
                    'project': self.project.pk,
                    'pk': self.hyperlink.pk}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['object'].pk, self.hyperlink.pk)


# Batch Editing View --------------------------------------------------------


class TestBatchEditView(TestViewsBase):
    """Tests for the batch editing view"""

    def test_render_delete(self):
        """Test rendering of the batch editing view when deleting"""
        post_data = {
            'batch_action': 'delete',
            'user_confirmed': '0'}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_Folder_{}'.format(self.folder.pk)] = 1
        post_data['batch_item_HyperLink_{}'.format(self.hyperlink.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

    def test_render_move(self):
        """Test rendering of the batch editing view when moving"""
        post_data = {
            'batch_action': 'move',
            'user_confirmed': '0'}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_HyperLink_{}'.format(self.hyperlink.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 200)

    def test_deletion(self):
        """Test batch object deletion"""

        # Assert preconditions
        self.assertEqual(File.objects.all().count(), 1)
        self.assertEqual(Folder.objects.all().count(), 1)
        self.assertEqual(HyperLink.objects.all().count(), 1)

        post_data = {
            'batch_action': 'delete',
            'user_confirmed': '1'}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_Folder_{}'.format(self.folder.pk)] = 1
        post_data['batch_item_HyperLink_{}'.format(self.hyperlink.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)

            # Assert postconditions
            self.assertEqual(File.objects.all().count(), 0)
            self.assertEqual(Folder.objects.all().count(), 0)
            self.assertEqual(HyperLink.objects.all().count(), 0)

    def test_deletion_non_empty_folder(self):
        """Test batch object deletion with a non-empty folder (should not be
        deleted)"""

        # Create new folder & file under folder
        new_folder = self._make_folder(
            'new_folder', self.project, None, self.user, '')

        new_file = self._make_file(
            name='new_file.txt',
            file_name='new_file.txt',
            file_content=self.file_content,
            project=self.project,
            folder=new_folder,  # Set new folder as parent
            owner=self.user,
            description='',
            public_url=True,
            secret='7dqq83clo2iyhg29hifbor56og6911r6')

        # Assert preconditions
        self.assertEqual(File.objects.all().count(), 2)
        self.assertEqual(Folder.objects.all().count(), 2)

        post_data = {
            'batch_action': 'delete',
            'user_confirmed': '1'}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_Folder_{}'.format(self.folder.pk)] = 1
        post_data['batch_item_Folder_{}'.format(new_folder.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)

            # Assert postconditions
            # The new folder and file should be left
            self.assertEqual(File.objects.all().count(), 1)
            self.assertEqual(Folder.objects.all().count(), 1)

    def test_moving(self):
        """Test batch object moving"""
        target_folder = self._make_folder(
            'target_folder', self.project, None, self.user, '')

        post_data = {
            'batch_action': 'move',
            'user_confirmed': '1',
            'target_folder': target_folder.pk}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_Folder_{}'.format(self.folder.pk)] = 1
        post_data['batch_item_HyperLink_{}'.format(self.hyperlink.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)

            # Assert postconditions
            self.assertEqual(
                File.objects.get(pk=self.file.pk).folder.pk,
                target_folder.pk)
            self.assertEqual(
                Folder.objects.get(pk=self.folder.pk).folder.pk,
                target_folder.pk)
            self.assertEqual(
                HyperLink.objects.get(pk=self.hyperlink.pk).folder.pk,
                target_folder.pk)

    def test_moving_name_exists(self):
        """Test batch object moving with similarly name object in target
        (should not be moved)"""

        # Create new folder & file
        target_folder = self._make_folder(
            'target_folder', self.project, None, self.user, '')

        new_file = self._make_file(
            name='file.txt',    # Same name as self.file
            file_name='file.txt',
            file_content=self.file_content,
            project=self.project,
            folder=target_folder,   # New file is under target
            owner=self.user,
            description='',
            public_url=True,
            secret='7dqq83clo2iyhg29hifbor56og6911r6')

        post_data = {
            'batch_action': 'move',
            'user_confirmed': '1',
            'target_folder': target_folder.pk}

        post_data['batch_item_File_{}'.format(self.file.pk)] = 1
        post_data['batch_item_Folder_{}'.format(self.folder.pk)] = 1
        post_data['batch_item_HyperLink_{}'.format(self.hyperlink.pk)] = 1

        with self.login(self.user):
            response = self.client.post(
                reverse('batch_edit', kwargs={'project': self.project.pk}),
                post_data)

            self.assertEqual(response.status_code, 302)

            # Assert postconditions
            self.assertEqual(
                File.objects.get(pk=self.file.pk).folder,
                None)   # Not moved
            self.assertEqual(
                Folder.objects.get(pk=self.folder.pk).folder.pk,
                target_folder.pk)
            self.assertEqual(
                HyperLink.objects.get(pk=self.hyperlink.pk).folder.pk,
                target_folder.pk)
