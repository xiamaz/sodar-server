"""Tests for Ajax API views in the samplesheets app"""

import json
import os

import fastobo
from altamisa.constants import table_headers as th

from django.conf import settings
from django.urls import reverse

# Projectroles dependency
from projectroles.models import SODAR_CONSTANTS
from projectroles.plugins import get_backend_api

# Ontologyaccess dependency
from ontologyaccess.io import OBOFormatOntologyIO
from ontologyaccess.models import DEFAULT_TERM_URL
from ontologyaccess.tests.test_io import OBO_PATH, OBO_NAME

# Timeline dependency
from timeline.models import ProjectEvent

from samplesheets.models import (
    Study,
    Assay,
    Protocol,
    Process,
    GenericMaterial,
    ISATab,
    IrodsAccessTicket,
    IrodsDataRequest,
)
from samplesheets.sheet_config import SheetConfigAPI
from samplesheets.tests.test_sheet_config import (
    SheetConfigMixin,
    CONFIG_STUDY_UUID,
)
from samplesheets.tests.test_views import (
    TestViewsBase,
    SHEET_DIR_SPECIAL,
    SHEET_PATH,
    SHEET_PATH_SMALL2,
    app_settings,
    EDIT_NEW_VALUE_STR,
    CONFIG_DATA_DEFAULT,
    SHEET_PATH_SMALL2_ALT,
)
from samplesheets.utils import get_node_obj, get_ext_link_labels
from samplesheets.views import SheetImportMixin
from samplesheets.views_ajax import ALERT_ACTIVE_REQS


conf_api = SheetConfigAPI()


# SODAR constants
PROJECT_TYPE_PROJECT = SODAR_CONSTANTS['PROJECT_TYPE_PROJECT']

# Local constants
APP_NAME = 'samplesheets'
EDIT_DIR = os.path.dirname(__file__) + '/edit/'
STUDY_INSERT_PATH = EDIT_DIR + 'i_small_study_insert.json'
ASSAY_INSERT_PATH = EDIT_DIR + 'i_small_assay_insert.json'
ASSAY_INSERT_SPLIT_PATH = EDIT_DIR + 'i_small_assay_insert_split.json'
ASSAY_INSERT_POOL_PATH = EDIT_DIR + 'i_small_assay_insert_pool.json'
STUDY_DELETE_PATH = EDIT_DIR + 'i_small_study_delete.json'
ASSAY_DELETE_PATH = EDIT_DIR + 'i_small_assay_delete.json'
EDIT_SOURCE_NAME = '0818'
EDIT_SOURCE_UUID = '11111111-1111-1111-1111-000000000000'
EDIT_STUDY_PROC_UUID = '11111111-1111-1111-1111-000000000001'
EDIT_SAMPLE_NAME = '0818-N1'
EDIT_SAMPLE_UUID = '11111111-1111-1111-5555-000000000000'
EMPTY_ONTOLOGY_VAL = {
    'unit': None,
    'value': {'name': None, 'accession': None, 'ontology_name': None},
}
SHEET_PATH_INSERTED = SHEET_DIR_SPECIAL + 'i_small_insert.zip'
TEST_FILE_NAME = 'test1'
IRODS_TICKET_STR = 'ooChaa1t'
VERSION_DESC = 'description'


class RowEditMixin:
    """Helpers for row insert/deletion"""

    def insert_row(self, path=None, data=None):
        """
        Insert row into database, based on file path or dictionary.

        :param path: String
        :param data: Dict
        :return: Response
        """
        if not path and not data:
            raise ValueError('Either path or data required')
        if path and data:
            raise ValueError('Provide either path or data')
        values = {'new_row': {}}
        if path:
            with open(path) as fp:
                values['new_row'] = json.load(fp)
        else:
            values['new_row'] = data
        with self.login(self.user):
            return self.client.post(
                reverse(
                    'samplesheets:ajax_edit_row_insert',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(values),
                content_type='application/json',
            )

    def delete_row(self, path):
        values = {'del_row': {}}
        with open(path) as fp:
            values['del_row'] = json.load(fp)
        with self.login(self.user):
            return self.client.post(
                reverse(
                    'samplesheets:ajax_edit_row_delete',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(values),
                content_type='application/json',
            )

    def update_assay_row_uuids(self, update_sample=True):
        """
        Update UUIDs for freshly added assay row, set self.row_uuids and
        self.row_names.
        """
        self.assay.refresh_from_db()
        # Update UUIDs in assay
        self.row_uuids = [
            '22222222-2222-2222-2222-00000000000' + str(i) for i in range(1, 8)
        ]
        self.row_names = []
        n_uuid = EDIT_SAMPLE_UUID
        u_name = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SAMPLE_NAME
        ).unique_name

        for i in range(len(self.row_uuids) + 1):
            if i > 0 or update_sample:
                obj = get_node_obj(study=self.study, unique_name=u_name)
                obj.sodar_uuid = n_uuid
                obj.save()
            if i < len(self.row_uuids):
                for a in self.assay.arcs:
                    if a[0] == u_name:
                        u_name = a[1]
                        self.row_names.append(a[1])
                        break
                n_uuid = self.row_uuids[i]


class IrodsAccessTicketMixin:
    """Helpers for creating IrodsAccessTicket object"""

    @classmethod
    def make_ticket(
        cls, path, user, project, assay, study, label=None, date_expires=None
    ):
        obj = IrodsAccessTicket(
            path=path,
            project=project,
            user=user,
            assay=assay,
            study=study,
            label=label,
            date_expires=date_expires,
        )
        obj.save()
        return obj


class TestContextAjaxView(TestViewsBase):
    """Tests for SheetContextAjaxView"""

    # TODO: Test with realistic ISA-Tab examples using BIH configs (see #434)

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.irods_backend = get_backend_api('omics_irods')
        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

    def test_get(self):
        """Test GET for context retrieval with sample sheets"""
        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.data)
        response_data.pop('csrf_token')  # HACK
        expected = {
            'configuration': self.investigation.get_configuration(),
            'inv_file_name': self.investigation.file_name.split('/')[-1],
            'irods_status': False,
            'irods_backend_enabled': True if self.irods_backend else False,
            'parser_version': self.investigation.parser_version,
            'parser_warnings': True
            if self.investigation.parser_warnings
            else False,
            'irods_webdav_enabled': settings.IRODS_WEBDAV_ENABLED,
            'irods_webdav_url': settings.IRODS_WEBDAV_URL,
            'external_link_labels': get_ext_link_labels(),
            'table_height': settings.SHEETS_TABLE_HEIGHT,
            'min_col_width': settings.SHEETS_MIN_COLUMN_WIDTH,
            'max_col_width': settings.SHEETS_MAX_COLUMN_WIDTH,
            'allow_editing': app_settings.get_default_setting(
                APP_NAME, 'allow_editing'
            ),
            'sheet_sync_enabled': app_settings.get_default_setting(
                APP_NAME, 'sheet_sync_enable'
            ),
            'alerts': [],
            'investigation': {
                'identifier': self.investigation.identifier,
                'title': self.investigation.title,
                'description': None,
                'comments': None,
            },
            'user_uuid': str(self.user.sodar_uuid),
            'studies': {
                str(self.study.sodar_uuid): {
                    'display_name': self.study.get_display_name(),
                    'identifier': self.study.identifier,
                    'description': self.study.description,
                    'comments': self.study.comments,
                    'irods_path': self.irods_backend.get_path(self.study),
                    'table_url': response.wsgi_request.build_absolute_uri(
                        reverse(
                            'samplesheets:ajax_study_tables',
                            kwargs={'study': str(self.study.sodar_uuid)},
                        )
                    ),
                    'plugin': None,
                    'assays': {
                        str(self.assay.sodar_uuid): {
                            'name': self.assay.get_name(),
                            'display_name': self.assay.get_display_name(),
                            'irods_path': self.irods_backend.get_path(
                                self.assay
                            ),
                            'display_row_links': True,
                            'plugin': None,
                        }
                    },
                }
            },
            'perms': {
                'edit_sheet': True,
                'manage_sheet': True,
                'create_colls': True,
                'export_sheet': True,
                'delete_sheet': True,
                'view_versions': True,
                'edit_config': True,
                'is_superuser': True,
            },
            'sheet_stats': {
                'study_count': Study.objects.filter(
                    investigation=self.investigation
                ).count(),
                'assay_count': Assay.objects.filter(
                    study__investigation=self.investigation
                ).count(),
                'protocol_count': Protocol.objects.filter(
                    study__investigation=self.investigation
                ).count(),
                'process_count': Process.objects.filter(
                    protocol__study__investigation=self.investigation
                ).count(),
                'source_count': self.investigation.get_material_count('SOURCE'),
                'material_count': self.investigation.get_material_count(
                    'MATERIAL'
                ),
                'sample_count': self.investigation.get_material_count('SAMPLE'),
                'data_count': self.investigation.get_material_count('DATA'),
            },
        }
        self.assertEqual(response_data, expected)

    def test_get_no_sheets(self):
        """Test GET for context retrieval without sample sheets"""
        self.investigation.active = False
        self.investigation.save()

        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.data)
        response_data.pop('csrf_token')  # HACK
        expected = {
            'configuration': None,
            'inv_file_name': None,
            'irods_status': None,
            'irods_backend_enabled': True if self.irods_backend else False,
            'parser_version': None,
            'parser_warnings': False,
            'irods_webdav_enabled': settings.IRODS_WEBDAV_ENABLED,
            'irods_webdav_url': settings.IRODS_WEBDAV_URL,
            'external_link_labels': None,
            'table_height': settings.SHEETS_TABLE_HEIGHT,
            'min_col_width': settings.SHEETS_MIN_COLUMN_WIDTH,
            'max_col_width': settings.SHEETS_MAX_COLUMN_WIDTH,
            'allow_editing': app_settings.get_default_setting(
                APP_NAME, 'allow_editing'
            ),
            'sheet_sync_enabled': app_settings.get_default_setting(
                APP_NAME, 'sheet_sync_enable'
            ),
            'alerts': [],
            'investigation': {},
            'user_uuid': str(self.user.sodar_uuid),
            'studies': {},
            'perms': {
                'edit_sheet': True,
                'manage_sheet': True,
                'create_colls': True,
                'export_sheet': True,
                'delete_sheet': True,
                'view_versions': True,
                'edit_config': True,
                'is_superuser': True,
            },
            'sheet_stats': {},
        }
        self.assertEqual(response_data, expected)

    # TODO: Test anonymous request and irods_webdav_enabled

    def test_get_as_delegate_min_owner(self):
        """Test GET as delegate with owner minimum role"""
        app_settings.set_app_setting(
            APP_NAME,
            'edit_config_min_role',
            SODAR_CONSTANTS['PROJECT_ROLE_OWNER'],
            project=self.project,
        )
        with self.login(self.user_delegate):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.json())['perms']['edit_config'])

    def test_get_as_delegate_min_delegate(self):
        """Test GET as delegate with delegate minimum role"""
        app_settings.set_app_setting(
            APP_NAME,
            'edit_config_min_role',
            SODAR_CONSTANTS['PROJECT_ROLE_DELEGATE'],
            project=self.project,
        )
        with self.login(self.user_delegate):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.json())['perms']['edit_config'])

    def test_get_irods_request_alert_owner(self):
        """Test GET with active iRODS request alert as owner"""
        self.investigation.irods_status = True
        self.investigation.save()
        # TODO: Use model helper instead (see #1088)
        IrodsDataRequest.objects.create(
            project=self.project,
            path=self.irods_backend.get_path(self.assay) + '/test/xxx.bam',
            user=self.user,
        )

        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data['alerts']), 1)
        self.assertEqual(
            response_data['alerts'][0]['html'],
            ALERT_ACTIVE_REQS.format(
                url=reverse(
                    'samplesheets:irods_requests',
                    kwargs={'project': self.project.sodar_uuid},
                )
            ),
        )

    def test_get_irods_request_alert_contributor(self):
        """Test GET with active iRODS request alert as contributor"""
        self.investigation.irods_status = True
        self.investigation.save()
        # TODO: Use model helper instead (see #1088)
        IrodsDataRequest.objects.create(
            project=self.project,
            path=self.irods_backend.get_path(self.assay) + '/test/xxx.bam',
            user=self.user,
        )
        contrib_user = self.make_user('user_contributor')
        self._make_assignment(self.project, contrib_user, self.role_contributor)

        with self.login(contrib_user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_context',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data['alerts']), 0)


class TestStudyTablesAjaxView(IrodsAccessTicketMixin, TestViewsBase):
    """Tests for StudyTablesAjaxView"""

    # TODO: Test with realistic ISA-Tab examples using BIH configs (see #434)

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Allow sample sheet editing in project
        app_settings.set_app_setting(
            APP_NAME, 'allow_editing', True, project=self.project
        )

    def test_get(self):
        """Test study tables retrieval"""
        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_study_tables',
                    kwargs={'study': self.study.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)

        ret_data = response.data
        self.assertIn('study', ret_data)
        self.assertIn('tables', ret_data)
        self.assertNotIn('render_error', ret_data)
        self.assertNotIn('shortcuts', ret_data['tables']['study'])
        self.assertEqual(len(ret_data['tables']['assays']), 1)
        self.assertNotIn(
            'uuid', ret_data['tables']['study']['table_data'][0][0]
        )
        self.assertIn('display_config', ret_data)
        self.assertNotIn('edit_context', ret_data)

    def test_get_edit(self):
        """Test study tables retrieval with edit mode enabled"""
        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_study_tables',
                    kwargs={'study': self.study.sodar_uuid},
                ),
                {'edit': 1},
            )
        self.assertEqual(response.status_code, 200)

        # Assert return data correctness
        ret_data = response.data
        self.assertIn('study', ret_data)
        self.assertIn('tables', ret_data)
        self.assertNotIn('render_error', ret_data)
        self.assertNotIn('shortcuts', ret_data['tables']['study'])
        self.assertEqual(len(ret_data['tables']['assays']), 1)
        self.assertIn('uuid', ret_data['tables']['study']['table_data'][0][0])
        self.assertIn('display_config', ret_data)
        self.assertIn('study_config', ret_data)
        self.assertIn('edit_context', ret_data)
        self.assertIn('sodar_ontologies', ret_data['edit_context'])
        self.assertIsNotNone(ret_data['edit_context']['samples'])
        self.assertIsNotNone(ret_data['edit_context']['protocols'])

    def test_get_track_hubs(self):
        """Test study tables retrieval with track hubs"""
        self.make_ticket(
            path='/some/path',
            project=self.project,
            assay=self.assay,
            study=self.study,
            user=self.user,
        )
        self.investigation.irods_status = True
        self.investigation.save()

        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_study_tables',
                    kwargs={'study': self.study.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)
        # TODO fill out ... assays are not yet tested, as well as shortcuts


class TestStudyLinksAjaxView(TestViewsBase):
    """Tests for StudyLinksAjaxView"""

    # TODO: Test with realistic ISA-Tab examples using BIH configs (see #434)

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

    def test_get(self):
        """Test study links retrieval without plugin"""
        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_study_links',
                    kwargs={'study': self.study.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 404)  # No plugin for ISA-Tab


class TestSheetWarningsAjaxView(TestViewsBase):
    """Tests for SheetWarningsAjaxView"""

    # TODO: Test with realistic ISA-Tab examples using BIH configs (see #434)

    def setUp(self):
        super().setUp()
        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)

    def test_get(self):
        """Test study tables retrieval"""
        with self.login(self.user):
            response = self.client.get(
                reverse(
                    'samplesheets:ajax_warnings',
                    kwargs={'project': self.project.sodar_uuid},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['warnings'], self.investigation.parser_warnings
        )


class TestSheetCellEditAjaxView(TestViewsBase):
    """Tests for SheetCellEditAjaxView"""

    @classmethod
    def _convert_ontology_value(cls, value):
        """
        Convert ontology value data sent in an edit request into a format
        expected in the database.
        NOTE: Regarding empty units, see issue #973
        """
        if isinstance(value, list) and len(value) == 1:
            value = {'value': value[0]}
        elif isinstance(value, list):
            value = {'value': value}
        if 'unit' not in value:
            value['unit'] = None
        return value

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()

        # Set up POST data
        self.values = {'updated_cells': []}

    def test_edit_name(self):
        """Test editing the name of a material"""
        obj = GenericMaterial.objects.get(study=self.study, name='0816')
        new_name = '0816aaa'
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'name',
                'header_type': 'name',
                'obj_cls': 'GenericMaterial',
                'value': new_name,
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.name, new_name)

    def test_edit_name_empty(self):
        """Test setting an empty material name (should fail)"""
        obj = GenericMaterial.objects.get(study=self.study, name='0816')
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'name',
                'header_type': 'name',
                'obj_cls': 'GenericMaterial',
                'value': '',
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 500)
        obj.refresh_from_db()
        self.assertEqual(obj.name, '0816')

    def test_edit_performer(self):
        """Test editing the performer of a process"""
        obj = Process.objects.filter(study=self.study, assay=None).first()
        value = 'Alice Example <alice@example.com>'
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'Performer',
                'header_type': 'performer',
                'obj_cls': 'Process',
                'value': value,
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.performer, value)

    def test_edit_perform_date(self):
        """Test editing the perform date of a process"""
        obj = Process.objects.filter(study=self.study, assay=None).first()
        value = '2020-07-07'
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'Perform date',
                'header_type': 'perform_date',
                'obj_cls': 'Process',
                'value': value,
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.perform_date.strftime('%Y-%m-%d'), value)

    def test_edit_perform_date_empty(self):
        """Test editing the perform date of a process with an empty date"""
        obj = Process.objects.filter(study=self.study, assay=None).first()
        value = ''
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'Perform date',
                'header_type': 'perform_date',
                'obj_cls': 'Process',
                'value': value,
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertIsNone(obj.perform_date)

    def test_edit_perform_date_invalid(self):
        """Test editing the perform date of a process with an invalid date"""
        obj = Process.objects.filter(study=self.study, assay=None).first()
        og_date = obj.perform_date
        value = '2020-11-31'
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'Perform date',
                'header_type': 'perform_date',
                'obj_cls': 'Process',
                'value': value,
            }
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 500)  # TODO: Should be 400?
        obj.refresh_from_db()
        self.assertEqual(obj.perform_date, og_date)

    def test_edit_characteristics_str(self):
        """Test editing a characteristics string value in a material"""
        obj = GenericMaterial.objects.get(study=self.study, name='0816')
        header_name = 'organism'
        self.assertNotEqual(
            obj.characteristics[header_name], EDIT_NEW_VALUE_STR
        )

        # TODO: Add complete set of params once they have been refactored
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': header_name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'value': EDIT_NEW_VALUE_STR,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            obj.characteristics[header_name],
            {'unit': None, 'value': EDIT_NEW_VALUE_STR},
        )

    def test_edit_param_values_str(self):
        """Test editing a parameter values string value in a process"""
        obj = Process.objects.filter(study=self.study, assay=None).first()
        header_name = 'instrument'
        self.assertNotEqual(
            obj.parameter_values[header_name], EDIT_NEW_VALUE_STR
        )

        # TODO: Add complete set of params once they have been refactored
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': header_name,
                'header_type': 'parameter_values',
                'obj_cls': 'Process',
                'value': EDIT_NEW_VALUE_STR,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            obj.parameter_values[header_name],
            {'unit': None, 'value': EDIT_NEW_VALUE_STR},
        )

    def test_edit_protocol(self):
        """Test editing the protocol reference of a process"""
        obj = Process.objects.filter(
            study=self.study, unique_name__icontains='sample collection'
        ).first()
        new_protocol = Protocol.objects.exclude(
            sodar_uuid=obj.protocol.sodar_uuid
        ).first()
        self.assertIsNotNone(new_protocol)
        self.assertNotEqual(obj.protocol, new_protocol)

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': 'protocol',
                'header_type': 'protocol',
                'obj_cls': 'Process',
                'value': new_protocol.name,
                'uuid_ref': str(new_protocol.sodar_uuid),
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.protocol, new_protocol)

    def test_edit_process_name(self):
        """Test editing the name of a process"""
        obj = Process.objects.filter(
            study=self.study, unique_name__icontains='sample collection'
        ).first()
        name_type = th.DATA_TRANSFORMATION_NAME
        name = 'New Process'
        self.assertNotEqual(obj.name, name)
        self.assertNotEqual(obj.name_type, name_type)

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name_type,
                'header_type': 'process_name',
                'obj_cls': 'Process',
                'value': name,
                'uuid_ref': str(obj.sodar_uuid),
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.name_type, name_type)

    def test_edit_ontology_term(self):
        """Test editing an ontology term with a single term"""
        obj = GenericMaterial.objects.get(study=self.study, name='0817')
        name = 'organism'
        self.assertEqual(obj.characteristics[name], EMPTY_ONTOLOGY_VAL)

        value = [
            {
                'name': 'Homo sapiens',
                'ontology_name': 'NCBITAXON',
                'accession': 'http://purl.bioontology.org/ontology/'
                'NCBITAXON/9606',
            }
        ]
        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'colType': 'ONTOLOGY',
                'value': value,
                'og_value': None,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            obj.characteristics[name], self._convert_ontology_value(value)
        )

    def test_edit_ontology_term_replace(self):
        """Test replacing an existing ontology term"""
        obj = GenericMaterial.objects.get(study=self.study, name='0815')
        name = 'organism'
        og_value = {
            'name': 'Mus musculus',
            'ontology_name': 'NCBITAXON',
            'accession': 'http://purl.bioontology.org/ontology/NCBITAXON/10090',
        }
        value = [
            {
                'name': 'Homo sapiens',
                'ontology_name': 'NCBITAXON',
                'accession': 'http://purl.bioontology.org/ontology/'
                'NCBITAXON/9606',
            }
        ]
        self.assertEqual(
            obj.characteristics[name], {'value': og_value, 'unit': None}
        )

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'colType': 'ONTOLOGY',
                'value': value,
                'og_value': [og_value],
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            obj.characteristics[name], self._convert_ontology_value(value)
        )

    def test_edit_ontology_term_list(self):
        """Test editing an ontology term with a list of terms"""
        obj = GenericMaterial.objects.get(study=self.study, name='0817')
        name = 'organism'
        value = [
            {
                'name': 'Homo sapiens',
                'ontology_name': 'NCBITAXON',
                'accession': 'http://purl.bioontology.org/ontology/'
                'NCBITAXON/9606',
            },
            {
                'name': 'Mus musculus',
                'ontology_name': 'NCBITAXON',
                'accession': 'http://purl.bioontology.org/ontology/'
                'NCBITAXON/10090',
            },
        ]
        self.assertEqual(obj.characteristics[name], EMPTY_ONTOLOGY_VAL)

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'colType': 'ONTOLOGY',
                'value': value,
                'og_value': None,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(
            obj.characteristics[name], self._convert_ontology_value(value)
        )

    def test_edit_ontology_term_empty(self):
        """Test editing an ontology term with an empty value"""
        obj = GenericMaterial.objects.get(study=self.study, name='0815')
        name = 'organism'
        og_value = {
            'name': 'Mus musculus',
            'ontology_name': 'NCBITAXON',
            'accession': 'http://purl.bioontology.org/ontology/NCBITAXON/10090',
        }
        self.assertNotEqual(obj.characteristics[name], EMPTY_ONTOLOGY_VAL)

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'colType': 'ONTOLOGY',
                'value': [],
                'og_value': og_value,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.characteristics[name], EMPTY_ONTOLOGY_VAL)

    def test_edit_ontology_term_ref(self):
        """Test ontology source ref updating when editing term value"""
        # Set up ontology
        obo_doc = fastobo.load(OBO_PATH)
        ontology = OBOFormatOntologyIO().import_obo(
            obo_doc=obo_doc, name=OBO_NAME, file=OBO_PATH
        )
        obj = GenericMaterial.objects.get(study=self.study, name='0817')
        name = 'organism'
        value = [
            {
                'name': 'Mus musculus',
                'ontology_name': 'NCBITAXON',
                'accession': 'http://purl.bioontology.org/ontology/'
                'NCBITAXON/10090',
            },
            {
                'name': 'Example term 0000002',
                'ontology_name': ontology.name,
                'accession': DEFAULT_TERM_URL.format(
                    id_space=ontology.name, local_id='0000002'
                ),
            },
        ]
        self.assertEqual(obj.characteristics[name], EMPTY_ONTOLOGY_VAL)
        self.assertEqual(len(self.investigation.ontology_source_refs), 4)

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name,
                'header_type': 'characteristics',
                'obj_cls': 'GenericMaterial',
                'colType': 'ONTOLOGY',
                'value': value,
                'og_value': None,
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.investigation.refresh_from_db()
        self.assertEqual(
            obj.characteristics[name], self._convert_ontology_value(value)
        )
        self.assertEqual(len(self.investigation.ontology_source_refs), 5)
        ref = next(
            r
            for r in self.investigation.ontology_source_refs
            if r['name'] == ontology.name
        )
        expected = {
            'file': ontology.file,
            'name': ontology.name,
            'version': ontology.data_version,
            'description': ontology.title,
            'comments': [],
            'headers': [
                'Term Source Name',
                'Term Source File',
                'Term Source Version',
                'Term Source Description',
            ],
        }
        self.assertEqual(ref, expected)


class TestSheetCellEditAjaxViewSpecial(TestViewsBase):
    """Tests for SheetCellEditAjaxView with special columns"""

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(
            SHEET_PATH_SMALL2, self.project
        )
        self.study = self.investigation.studies.first()

        # Set up POST data
        self.values = {'updated_cells': []}

    def test_edit_extract_label_string(self):
        """Test updating the extract label field with a string value"""
        label = 'New label'
        name_type = th.LABELED_EXTRACT_NAME
        obj = GenericMaterial.objects.get(
            study=self.study, name='0815-N1-Pro1-A-114'
        )
        self.assertEqual(obj.extract_label, 'iTRAQ reagent 114')

        self.values['updated_cells'].append(
            {
                'uuid': str(obj.sodar_uuid),
                'header_name': name_type,
                'header_type': 'extract_label',
                'obj_cls': 'GenericMaterial',
                'value': label,
                'uuid_ref': str(obj.sodar_uuid),
            }
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_cell',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.extract_label, label)


class TestSheetRowInsertAjaxView(RowEditMixin, SheetConfigMixin, TestViewsBase):
    """Tests for SheetRowInsertAjaxView"""

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        # Set up UUIDs and default config
        self._update_uuids(self.investigation, CONFIG_DATA_DEFAULT)
        app_settings.set_app_setting(
            APP_NAME,
            'sheet_config',
            conf_api.build_sheet_config(self.investigation),
            project=self.project,
        )
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

    def test_insert_study_row(self):
        """Test inserting a new row into a study"""
        self.assertIsNone(
            GenericMaterial.objects.filter(
                study=self.study, name='0818'
            ).first()
        )

        process_pks = [
            p.pk for p in Process.objects.filter(study=self.study, assay=None)
        ]
        protocol = Protocol.objects.get(
            study=self.study, name='sample collection'
        )
        mat_count = GenericMaterial.objects.filter(
            study=self.study, assay=None
        ).count()
        proc_count = Process.objects.filter(
            study=self.study, assay=None
        ).count()

        # Insert row
        response = self.insert_row(path=STUDY_INSERT_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            GenericMaterial.objects.filter(
                study=self.study, assay=None
            ).count(),
            mat_count + 2,
        )
        self.assertEqual(
            Process.objects.filter(study=self.study, assay=None).count(),
            proc_count + 1,
        )

        source = GenericMaterial.objects.get(
            study=self.study, name='0818', item_type='SOURCE'
        )
        self.assertEqual(source.characteristics['age']['value'], '170')
        self.assertEqual(source.characteristics['age']['unit']['name'], 'day')

        process = (
            Process.objects.filter(study=self.study, assay=None)
            .exclude(pk__in=process_pks)
            .first()
        )
        self.assertIsNotNone(process)
        self.assertEqual(process.protocol, protocol)
        self.assertEqual(
            process.parameter_values['instrument']['value'], 'scalpel'
        )
        self.assertEqual(process.performer, 'John Doe')
        self.assertEqual(
            process.perform_date.strftime('%Y-%m-%d'), '2020-09-03'
        )

        sample = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SAMPLE_NAME, item_type='SAMPLE'
        )
        self.assertEqual(sample.characteristics['status']['value'], '0')
        self.assertEqual(sample.factor_values['treatment']['value'], 'yes')

    def test_insert_assay_row(self):
        """Test inserting a new row into an assay"""
        # Insert study row
        response = self.insert_row(path=STUDY_INSERT_PATH)
        self.assertEqual(response.status_code, 200)
        # Update sample UUID
        sample = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SAMPLE_NAME
        )
        sample.sodar_uuid = EDIT_SAMPLE_UUID
        sample.save()

        mat_count = GenericMaterial.objects.filter(assay=self.assay).count()
        proc_count = Process.objects.filter(assay=self.assay).count()
        arc_count = len(self.assay.arcs)

        # Insert assay row
        response = self.insert_row(path=ASSAY_INSERT_PATH)

        self.assertEqual(response.status_code, 200)
        self.assay.refresh_from_db()

        self.assertEqual(
            GenericMaterial.objects.filter(assay=self.assay).count(),
            mat_count + 4,
        )
        self.assertEqual(
            Process.objects.filter(assay=self.assay).count(),
            proc_count + 3,
        )
        self.assertEqual(
            GenericMaterial.objects.filter(
                name=EDIT_SOURCE_NAME, item_type='SOURCE'
            ).count(),
            1,
        )
        self.assertEqual(
            GenericMaterial.objects.filter(
                name=EDIT_SAMPLE_NAME, item_type='SAMPLE'
            ).count(),
            1,
        )
        self.assertEqual(len(self.assay.arcs), arc_count + 7)

        node_names = []
        for uuid in response.data['node_uuids']:
            obj = GenericMaterial.objects.filter(sodar_uuid=uuid).first()
            if not obj:
                obj = Process.objects.filter(sodar_uuid=uuid).first()
            self.assertIsNotNone(obj)
            node_names.append(obj.unique_name)
        for i in range(len(node_names) - 1):
            self.assertIn([node_names[i], node_names[i + 1]], self.assay.arcs)

    def test_insert_assay_row_split(self):
        """Test inserting a row with splitting into an assay"""
        # Insert study and assay rows
        self.insert_row(path=STUDY_INSERT_PATH)
        sample = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SAMPLE_NAME
        )
        sample.sodar_uuid = EDIT_SAMPLE_UUID
        sample.save()
        self.insert_row(path=ASSAY_INSERT_PATH)

        self.update_assay_row_uuids(update_sample=False)
        mat_count = GenericMaterial.objects.filter(assay=self.assay).count()
        proc_count = Process.objects.filter(assay=self.assay).count()
        arc_count = len(self.assay.arcs)

        # Insert new row
        response = self.insert_row(path=ASSAY_INSERT_SPLIT_PATH)

        self.assertEqual(response.status_code, 200)
        self.assay.refresh_from_db()
        self.assertEqual(
            GenericMaterial.objects.filter(assay=self.assay).count(),
            mat_count + 1,
        )
        self.assertEqual(
            Process.objects.filter(assay=self.assay).count(), proc_count
        )
        self.assertEqual(len(self.assay.arcs), arc_count + 1)

    def test_insert_assay_row_pool(self):
        """Test inserting a row with pooling into an assay"""
        self.insert_row(path=STUDY_INSERT_PATH)
        sample = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SAMPLE_NAME
        )
        sample.sodar_uuid = EDIT_SAMPLE_UUID
        sample.save()
        self.insert_row(path=ASSAY_INSERT_PATH)

        self.update_assay_row_uuids(update_sample=False)
        mat_count = GenericMaterial.objects.filter(assay=self.assay).count()
        proc_count = Process.objects.filter(assay=self.assay).count()
        arc_count = len(self.assay.arcs)

        # Insert new row
        response = self.insert_row(path=ASSAY_INSERT_POOL_PATH)

        self.assertEqual(response.status_code, 200)
        self.assay.refresh_from_db()
        self.assertEqual(
            GenericMaterial.objects.filter(assay=self.assay).count(),
            mat_count + 3,
        )
        self.assertEqual(
            Process.objects.filter(assay=self.assay).count(), proc_count + 3
        )
        self.assertEqual(len(self.assay.arcs), arc_count + 7)

    # TODO: Test ontology ref updating


class TestSheetRowDeleteAjaxView(RowEditMixin, SheetConfigMixin, TestViewsBase):
    """Tests for SheetRowDeleteAjaxView"""

    def setUp(self):
        super().setUp()

        # Import investigation where extra rows have been inserted
        self.investigation = self.import_isa_from_file(
            SHEET_PATH_INSERTED, self.project
        )
        # Set up UUIDs and default config
        self._update_uuids(self.investigation, CONFIG_DATA_DEFAULT)
        app_settings.set_app_setting(
            APP_NAME,
            'sheet_config',
            conf_api.build_sheet_config(self.investigation),
            project=self.project,
        )
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()

        # Update UUIDs in study
        source = GenericMaterial.objects.get(
            study=self.study, name=EDIT_SOURCE_NAME
        )
        source.sodar_uuid = EDIT_SOURCE_UUID
        source.save()

        proc = (
            Process.objects.filter(
                study=self.study, assay=None, protocol__name='sample collection'
            )
            .order_by('-pk')
            .first()
        )
        proc.sodar_uuid = EDIT_STUDY_PROC_UUID
        proc.save()

        # Update UUIDs in assay
        self.update_assay_row_uuids()

    def test_delete_assay_row(self):
        """Test row deletion from assay"""
        response = self.delete_row(ASSAY_DELETE_PATH)
        self.assertEqual(response.status_code, 200)
        self.assay.refresh_from_db()
        self.assertIsNotNone(
            GenericMaterial.objects.filter(
                study=self.study, name=EDIT_SAMPLE_NAME
            ).first()
        )
        for u in self.row_uuids:
            self.assertIsNone(get_node_obj(study=self.study, sodar_uuid=u))
        target_nodes = [a[1] for a in self.assay.arcs]
        for n in self.row_names:
            self.assertNotIn(n, target_nodes)

    def test_delete_study_row(self):
        """Test row deletion from study"""
        # First delete the assay row
        response = self.delete_row(ASSAY_DELETE_PATH)
        self.assertEqual(response.status_code, 200)
        # Delete the study row
        response = self.delete_row(STUDY_DELETE_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            GenericMaterial.objects.filter(
                study=self.study, name=EDIT_SAMPLE_NAME
            ).first()
        )
        self.assertIsNone(
            Process.objects.filter(
                study=self.study, sodar_uuid=EDIT_STUDY_PROC_UUID
            ).first()
        )
        self.assertIsNone(
            GenericMaterial.objects.filter(
                study=self.study, name=EDIT_SOURCE_NAME
            ).first()
        )

    def test_delete_study_row_in_use(self):
        """Test study row deletion with sample used in asssay (should fail)"""
        response = self.delete_row(STUDY_DELETE_PATH)
        self.assertEqual(response.status_code, 500)
        self.assertIsNotNone(
            GenericMaterial.objects.filter(
                study=self.study, name=EDIT_SAMPLE_NAME
            ).first()
        )
        self.assertIsNotNone(
            Process.objects.filter(
                study=self.study, sodar_uuid=EDIT_STUDY_PROC_UUID
            ).first()
        )
        self.assertIsNotNone(
            GenericMaterial.objects.filter(
                study=self.study, name=EDIT_SOURCE_NAME
            ).first()
        )

    # TODO: Test deletion with splitting/pooling


class TestSheetVersionSaveAjaxView(TestViewsBase):
    """Tests for SheetVersionSaveAjaxView"""

    def setUp(self):
        super().setUp()
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()

    def test_post(self):
        """Test POST"""
        self.assertEqual(ISATab.objects.count(), 1)
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_version_save',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps({'save': True, 'description': VERSION_DESC}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ISATab.objects.count(), 2)
        new_version = ISATab.objects.order_by('-pk').first()
        self.assertEqual(new_version.description, VERSION_DESC)


class TestSheetEditFinishAjaxView(TestViewsBase):
    """Tests for SheetEditFinishAjaxView"""

    def setUp(self):
        super().setUp()
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()

    def test_post(self):
        """Test POST with updates=True"""
        self.assertEqual(ISATab.objects.count(), 1)
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_finish',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps({'updated': True, 'version_saved': False}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ISATab.objects.count(), 2)

    def test_post_version_saved(self):
        """Test POST with version_saved=True"""
        self.assertEqual(ISATab.objects.count(), 1)
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_finish',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps({'updated': True, 'version_saved': True}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ISATab.objects.count(), 1)  # No new version

    def test_post_no_updates(self):
        """Test POST with updates=False"""
        self.assertEqual(ISATab.objects.count(), 1)
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_edit_finish',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps({'updated': False, 'version_saved': True}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ISATab.objects.count(), 1)


class TestSheetEditConfigAjaxView(SheetConfigMixin, TestViewsBase):
    """Tests for SheetEditConfigAjaxView"""

    # TODO: Test with assay updates (needs a better test ISA-Tab)

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        # Set up UUIDs and default config
        self._update_uuids(self.investigation, CONFIG_DATA_DEFAULT)
        app_settings.set_app_setting(
            APP_NAME,
            'sheet_config',
            conf_api.build_sheet_config(self.investigation),
            project=self.project,
        )
        app_settings.set_app_setting(
            APP_NAME,
            'edit_config_min_role',
            SODAR_CONSTANTS['PROJECT_ROLE_OWNER'],
            project=self.project,
        )
        self.study = self.investigation.studies.first()
        self.assay = self.study.assays.first()
        self.post_values = {
            'fields': [
                {
                    'action': 'update',
                    'study': CONFIG_STUDY_UUID,
                    'assay': None,
                    'node_idx': 0,
                    'field_idx': 2,
                    'config': {
                        'name': 'age',
                        'type': 'characteristics',
                        'editable': True,
                        'format': 'integer',
                        'range': [None, None],
                        'regex': '',
                        'default': '',
                        'unit': ['day'],
                        'unit_default': 'day',
                    },
                }
            ]
        }

    def test_update_study_column(self):
        """Test posting a study column update"""
        sheet_config = app_settings.get_app_setting(
            APP_NAME, 'sheet_config', project=self.project
        )
        self.assertEqual(sheet_config, CONFIG_DATA_DEFAULT)
        self.assertEqual(
            ProjectEvent.objects.filter(
                project=self.project,
                app=APP_NAME,
                event_name='field_update',
            ).count(),
            0,
        )

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_config_update',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.post_values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)

        sheet_config = app_settings.get_app_setting(
            APP_NAME, 'sheet_config', project=self.project
        )
        expected = {
            'name': 'age',
            'type': 'characteristics',
            'editable': True,
            'format': 'integer',
            'regex': '',
            'default': '',
            'unit': ['day'],
            'unit_default': 'day',
        }
        self.assertEqual(
            sheet_config['studies'][CONFIG_STUDY_UUID]['nodes'][0]['fields'][2],
            expected,
        )
        self.assertEqual(
            ProjectEvent.objects.filter(
                project=self.project,
                app=APP_NAME,
                event_name='field_update',
            ).count(),
            1,
        )

    def test_update_as_superuser_min_owner(self):
        """Test updating as superuser with minimum role of owner"""
        edit_config_min_role = app_settings.get_app_setting(
            APP_NAME, 'edit_config_min_role', project=self.project
        )
        self.assertEqual(
            edit_config_min_role, SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
        )
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_config_update',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.post_values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)

    def test_update_as_owner_min_owner(self):
        """Test updating as owner with minimum role of owner"""
        edit_config_min_role = app_settings.get_app_setting(
            APP_NAME, 'edit_config_min_role', project=self.project
        )
        self.assertEqual(
            edit_config_min_role, SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
        )
        with self.login(self.user_owner):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_config_update',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.post_values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)

    def test_update_as_delegate_min_owner(self):
        """Test updating as delegate with minimum role of owner (should fail)"""
        edit_config_min_role = app_settings.get_app_setting(
            APP_NAME, 'edit_config_min_role', project=self.project
        )
        self.assertEqual(
            edit_config_min_role, SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
        )
        with self.login(self.user_delegate):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_config_update',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.post_values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()['detail'],
            'User not allowed to modify column config',
        )

    def test_update_as_contributor_min_owner(self):
        """Test updating as contributor with minimum role of owner (should fail)"""
        edit_config_min_role = app_settings.get_app_setting(
            APP_NAME, 'edit_config_min_role', project=self.project
        )
        self.assertEqual(
            edit_config_min_role, SODAR_CONSTANTS['PROJECT_ROLE_OWNER']
        )
        with self.login(self.user_contributor):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_config_update',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                json.dumps(self.post_values),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()['detail'],
            'User not allowed to modify column config',
        )


class TestStudyDisplayConfigAjaxView(TestViewsBase):
    """Tests for StudyDisplayConfigAjaxView"""

    def setUp(self):
        super().setUp()

        # Import investigation
        self.investigation = self.import_isa_from_file(SHEET_PATH, self.project)
        self.study = self.investigation.studies.first()
        self.s_uuid = str(self.investigation.studies.first().sodar_uuid)
        self.a_uuid = str(
            self.investigation.studies.first().assays.first().sodar_uuid
        )
        # Build sheet config and default display config
        self.sheet_config = conf_api.build_sheet_config(self.investigation)
        self.display_config = conf_api.build_display_config(
            self.investigation, self.sheet_config
        )
        app_settings.set_app_setting(
            APP_NAME,
            'display_config_default',
            project=self.project,
            value=self.display_config,
        )
        app_settings.set_app_setting(
            APP_NAME,
            'display_config',
            project=self.project,
            user=self.user,
            value=self.display_config,
        )
        self.study_config = self.display_config['studies'][self.s_uuid]

    def test_post(self):
        """Test updating the sheet configuration"""
        self.assertEqual(
            self.study_config['nodes'][0]['fields'][2]['visible'], True
        )
        self.study_config['nodes'][0]['fields'][2]['visible'] = False

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_display_update',
                    kwargs={'study': self.study.sodar_uuid},
                ),
                json.dumps(
                    {'study_config': self.study_config, 'set_default': False}
                ),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'ok')
        updated_config = app_settings.get_app_setting(
            APP_NAME, 'display_config', project=self.project, user=self.user
        )
        self.assertEqual(
            updated_config['studies'][self.s_uuid]['nodes'][0]['fields'][2][
                'visible'
            ],
            False,
        )

    def test_post_default(self):
        """Test updating along with the default configuration"""
        self.assertEqual(
            self.study_config['nodes'][0]['fields'][2]['visible'], True
        )
        self.study_config['nodes'][0]['fields'][2]['visible'] = False

        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_display_update',
                    kwargs={'study': self.study.sodar_uuid},
                ),
                json.dumps(
                    {'study_config': self.study_config, 'set_default': True}
                ),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'ok')
        updated_config = app_settings.get_app_setting(
            APP_NAME, 'display_config', project=self.project, user=self.user
        )
        default_config = app_settings.get_app_setting(
            APP_NAME, 'display_config_default', project=self.project
        )
        self.assertEqual(
            updated_config['studies'][self.s_uuid]['nodes'][0]['fields'][2][
                'visible'
            ],
            False,
        )
        self.assertEqual(updated_config, default_config)

    def test_post_no_change(self):
        """Test posting with no updates"""
        with self.login(self.user):
            response = self.client.post(
                reverse(
                    'samplesheets:ajax_display_update',
                    kwargs={'study': self.study.sodar_uuid},
                ),
                json.dumps(
                    {'study_config': self.study_config, 'set_default': False}
                ),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data['detail'], 'ok')
        updated_config = app_settings.get_app_setting(
            APP_NAME, 'display_config', project=self.project, user=self.user
        )
        self.assertEqual(
            updated_config,
            self.display_config,
        )


class TestSheetVersionCompareAjaxView(SheetImportMixin, TestViewsBase):
    """Tests for SheetVersionCompareAjaxView"""

    def setUp(self):
        super().setUp()
        self.import_isa_from_file(SHEET_PATH_SMALL2, self.project)

        with open(SHEET_PATH_SMALL2_ALT, 'rb') as file, self.login(self.user):
            values = {'file_upload': file}
            self.client.post(
                reverse(
                    'samplesheets:import',
                    kwargs={'project': self.project.sodar_uuid},
                ),
                values,
            )

        self.isa1 = ISATab.objects.first()
        self.isa2 = ISATab.objects.last()
        self.isa2.data['studies']['s_small2.txt'] = self.isa2.data[
            'studies'
        ].pop('s_small2_alt.txt')
        self.isa2.data['assays']['a_small2.txt'] = self.isa2.data['assays'].pop(
            'a_small2_alt.txt'
        )
        self.isa2.save()

    def test_get(self):
        """Test GET returning diff data"""
        expected = {
            'studies': {
                's_small2.txt': [
                    [
                        line.split('\t')
                        for line in self.isa1.data['studies']['s_small2.txt'][
                            'tsv'
                        ].split('\n')
                    ],
                    [
                        line.split('\t')
                        for line in self.isa2.data['studies']['s_small2.txt'][
                            'tsv'
                        ].split('\n')
                    ],
                ]
            },
            'assays': {
                'a_small2.txt': [
                    [
                        line.split('\t')
                        for line in self.isa1.data['assays']['a_small2.txt'][
                            'tsv'
                        ].split('\n')
                    ],
                    [
                        line.split('\t')
                        for line in self.isa2.data['assays']['a_small2.txt'][
                            'tsv'
                        ].split('\n')
                    ],
                ]
            },
        }

        with self.login(self.user):
            response = self.client.get(
                '{}?source={}&target={}'.format(
                    reverse(
                        'samplesheets:ajax_version_compare',
                        kwargs={'project': self.project.sodar_uuid},
                    ),
                    str(self.isa1.sodar_uuid),
                    str(self.isa2.sodar_uuid),
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_get_no_permission(self):
        """Test GET without permission"""
        expected = {
            'detail': 'You do not have permission to perform this action.'
        }
        with self.login(self.user_guest):
            response = self.client.get(
                '{}?source={}&target={}'.format(
                    reverse(
                        'samplesheets:ajax_version_compare',
                        kwargs={'project': self.project.sodar_uuid},
                    ),
                    str(self.isa1.sodar_uuid),
                    str(self.isa2.sodar_uuid),
                )
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), expected)

    def test_get_no_sheets(self):
        """Test GET without permission"""
        expected = {'detail': 'Sample sheet version(s) not found.'}
        with self.login(self.user):
            response = self.client.get(
                '{}?source={}&target={}'.format(
                    reverse(
                        'samplesheets:ajax_version_compare',
                        kwargs={'project': self.project.sodar_uuid},
                    ),
                    str(self.isa1.sodar_uuid),
                    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                )
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), expected)

    def test_get_studies_file(self):
        """Test GET returning diff data for studies file"""
        expected = [
            [
                line.split('\t')
                for line in self.isa1.data['studies']['s_small2.txt'][
                    'tsv'
                ].split('\n')
            ],
            [
                line.split('\t')
                for line in self.isa2.data['studies']['s_small2.txt'][
                    'tsv'
                ].split('\n')
            ],
        ]

        with self.login(self.user):
            response = self.client.get(
                '{}?source={}&target={}&filename={}&category={}'.format(
                    reverse(
                        'samplesheets:ajax_version_compare',
                        kwargs={'project': self.project.sodar_uuid},
                    ),
                    str(self.isa1.sodar_uuid),
                    str(self.isa2.sodar_uuid),
                    's_small2.txt',
                    'studies',
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_get_assays_file(self):
        """Test GET returning diff data for assays file"""
        expected = [
            [
                line.split('\t')
                for line in self.isa1.data['assays']['a_small2.txt'][
                    'tsv'
                ].split('\n')
            ],
            [
                line.split('\t')
                for line in self.isa2.data['assays']['a_small2.txt'][
                    'tsv'
                ].split('\n')
            ],
        ]

        with self.login(self.user):
            response = self.client.get(
                '{}?source={}&target={}&filename={}&category={}'.format(
                    reverse(
                        'samplesheets:ajax_version_compare',
                        kwargs={'project': self.project.sodar_uuid},
                    ),
                    str(self.isa1.sodar_uuid),
                    str(self.isa2.sodar_uuid),
                    'a_small2.txt',
                    'assays',
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
