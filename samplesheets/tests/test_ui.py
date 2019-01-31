"""UI tests for the samplesheets app"""

from django.urls import reverse

# Projectroles dependency
from projectroles.tests.test_ui import TestUIBase

from .test_io import SampleSheetIOMixin, SHEET_DIR


# Local constants
SHEET_PATH = SHEET_DIR + 'i_small.zip'


class TestProjectSheetsView(SampleSheetIOMixin, TestUIBase):
    """Tests for the project sheets view UI"""

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self._import_isa_from_file(
            SHEET_PATH, self.project
        )
        self.study = self.investigation.studies.first()

    # TODO: Temporarily disabled, see issue #125
    '''
    def test_tables(self):
        """Test existence of tables in the view after import"""
        expected = [
            (self.superuser, 2),
            (self.as_owner.user, 2),
            (self.as_delegate.user, 2),
            (self.as_contributor.user, 2),
            (self.as_guest.user, 2)]
        url = reverse(
            'samplesheets:project_sheets',
            kwargs={'project': self.project.sodar_uuid})
        self.assert_element_count(expected, url, 'sodar-ss-data-table')
    '''

    def test_nav(self):
        """Test existence of navigation menu items in the view"""
        expected = [
            (self.superuser, 3),
            (self.as_owner.user, 3),
            (self.as_delegate.user, 3),
            (self.as_contributor.user, 3),
            (self.as_guest.user, 3),
        ]
        url = reverse(
            'samplesheets:project_sheets',
            kwargs={'project': self.project.sodar_uuid},
        )
        self.assert_element_count(
            expected, url, 'sodar-ss-nav-item', attribute='class'
        )

    def test_operations(self):
        """Test existence of operations buttons in the view"""
        expected_true = [
            self.superuser,
            self.as_owner.user,
            self.as_delegate.user,
            self.as_contributor.user,
        ]
        expected_false = [self.as_guest.user]
        url = reverse(
            'samplesheets:project_sheets',
            kwargs={'project': self.project.sodar_uuid},
        )

        self.assert_element_exists(
            expected_true, url, 'sodar-ss-buttons-op', True
        )

        self.assert_element_exists(
            expected_false, url, 'sodar-ss-buttons-op', False
        )

    def test_export_button(self):
        """Test existence of TSV export buttons in the view"""
        expected = [
            (self.superuser, 2),
            (self.as_owner.user, 2),
            (self.as_delegate.user, 2),
            (self.as_contributor.user, 2),
            (self.as_guest.user, 0),
        ]
        url = reverse(
            'samplesheets:project_sheets',
            kwargs={'project': self.project.sodar_uuid},
        )
        self.assert_element_count(
            expected, url, 'sodar-ss-data-excel', attribute='class'
        )
