"""Sample sheet edit and display configuration management"""
import logging
from packaging import version

from django.conf import settings

# Projectroles dependency
from projectroles.app_settings import AppSettingAPI

from samplesheets.rendering import SampleSheetTableBuilder


# Get logger
logger = logging.getLogger(__name__)

# App settings API
app_settings = AppSettingAPI()


# Local constants
APP_NAME = 'samplesheets'


class SheetConfigAPI:
    """API for sample sheet edit and display configuration management"""

    def get_sheet_config(self, investigation):
        """
        Get or build a sheet edit configuration for an investigation.

        :param investigation: Investigation object
        :return: Dict
        """
        sheet_config = app_settings.get_app_setting(
            APP_NAME, 'sheet_config', project=investigation.project
        )
        sheet_ok = False

        if sheet_config:
            try:
                self.validate_sheet_config(sheet_config)
                sheet_ok = True

            except ValueError as ex:
                # TODO: Implement updating invalid configs if possible?
                msg = 'Invalid config, rebuilding.. Exception: "{}"'.format(ex)

        else:
            msg = 'No sheet configuration found, building..'

        if not sheet_ok:
            logger.info(msg)
            sheet_config = self.build_sheet_config(investigation)
            app_settings.set_app_setting(
                APP_NAME,
                'sheet_config',
                sheet_config,
                project=investigation.project,
            )
            logger.info(
                'Sheet configuration built for investigation (UUID={})'.format(
                    investigation.sodar_uuid
                )
            )

        return sheet_config

    @classmethod
    def build_sheet_config(cls, investigation):
        """
        Build sample sheet edit configuration.
        NOTE: Will be built from configuration template(s) eventually

        :param investigation: Investigation object
        :return: Dict
        """
        tb = SampleSheetTableBuilder()
        ret = {
            'version': settings.SHEETS_CONFIG_VERSION,
            'investigation': {},
            'studies': {},
        }

        def _build_nodes(study_tables, assay_uuid=None):
            from samplesheets.models import Protocol

            nodes = []
            sample_found = False
            ti = 0

            if not assay_uuid:
                table = study_tables['study']

            else:
                table = study_tables['assays'][assay_uuid]

            for th in table['top_header']:
                if not assay_uuid or sample_found:
                    node = {'header': th['value'], 'fields': []}

                    for i in range(ti, ti + th['colspan']):
                        h = table['field_header'][i]
                        f = {'name': h['name']}

                        if h['type']:
                            f['type'] = h['type']

                        # Set up default protocol if only one option in data
                        if h['type'] == 'protocol':
                            p_name = None
                            p_found = False
                            protocol = None

                            for row in table['table_data']:
                                if not p_name and row[i]['value']:
                                    p_name = row[i]['value']
                                    p_found = True

                                elif p_name and row[i]['value'] != p_name:
                                    p_found = False
                                    break

                            if p_found:
                                protocol = Protocol.objects.filter(
                                    study__investigation=investigation,
                                    name=p_name,
                                ).first()

                            if protocol:
                                f['default'] = str(protocol.sodar_uuid)
                                f['format'] = 'protocol'

                        node['fields'].append(f)

                    nodes.append(node)

                # Leave out study columns for assays
                if assay_uuid and th['value'] == 'Sample':
                    sample_found = True

                ti += th['colspan']

            return nodes

        # Add studies
        for study in investigation.studies.all().order_by('pk'):
            # Build tables (disable use_config in case we are replacing sheets)
            study_tables = tb.build_study_tables(
                study, edit=True, use_config=False
            )
            study_data = {
                'display_name': study.get_display_name(),
                # For human readability
                'nodes': _build_nodes(study_tables, None),
                'assays': {},
            }

            # Add study assays
            for assay in study.assays.all().order_by('pk'):
                assay_uuid = str(assay.sodar_uuid)
                study_data['assays'][assay_uuid] = {
                    'display_name': assay.get_display_name(),
                    'nodes': _build_nodes(study_tables, assay_uuid),
                }

            ret['studies'][str(study.sodar_uuid)] = study_data

        return ret

    @classmethod
    def validate_sheet_config(cls, config):
        """
        Validate sheet edit configuration.

        :param config: Dict
        :raise: ValueError if config is invalid.
        """
        if not config:
            raise ValueError('No configuration provided')

        if not config.get('version'):
            raise ValueError('Unknown configuration version')

        cfg_version = version.parse(config['version'])
        min_version = version.parse(settings.SHEETS_CONFIG_VERSION)

        if cfg_version < min_version:
            raise ValueError(
                'Version "{}" is below minimum version "{}"'.format(
                    cfg_version, min_version
                )
            )

    @classmethod
    def build_display_config(cls, investigation, sheet_config):
        """
        Build default display config for project sample sheet columns.

        :param investigation: Investigation object
        :param sheet_config: Sheet editing configuration (dict)
        :return: Dict
        """
        tb = SampleSheetTableBuilder()
        ret = {'investigation': {}, 'studies': {}}

        def _build_node(config_node, table, idx, assay_mode=False):
            display_node = {'header': config_node['header'], 'fields': []}
            n_idx = 0

            for config_field in config_node['fields']:
                display_field = {'name': config_field['name'], 'visible': False}

                if n_idx == 0 or (
                    not assay_mode
                    and (
                        config_field.get('editable')
                        or table['col_values'][idx] > 0
                    )
                ):
                    display_field['visible'] = True

                display_node['fields'].append(display_field)
                idx += 1
                n_idx += 1

            return display_node, idx

        # Add studies
        for study in investigation.studies.all().order_by('pk'):
            study_uuid = str(study.sodar_uuid)
            study_tables = tb.build_study_tables(
                study, edit=False, use_config=False
            )
            h_idx = 0
            study_data = {'nodes': [], 'assays': {}}

            for config_node in sheet_config['studies'][study_uuid]['nodes']:
                display_node, h_idx = _build_node(
                    config_node, study_tables['study'], h_idx
                )
                study_data['nodes'].append(display_node)

            # Add study assays
            for assay in study.assays.all().order_by('pk'):
                assay_uuid = str(assay.sodar_uuid)
                assay_table = study_tables['assays'][assay_uuid]
                h_idx = 0
                assay_data = {'nodes': []}

                # Add study nodes to assay table with only first field visible
                for config_node in sheet_config['studies'][study_uuid]['nodes']:
                    node, h_idx = _build_node(
                        config_node,
                        study_tables['study'],
                        h_idx,
                        assay_mode=True,
                    )
                    assay_data['nodes'].append(node)

                # Add actual assay nodes
                for config_node in sheet_config['studies'][study_uuid][
                    'assays'
                ][assay_uuid]['nodes']:
                    node, h_idx = _build_node(config_node, assay_table, h_idx)
                    assay_data['nodes'].append(node)

                study_data['assays'][assay_uuid] = assay_data

            ret['studies'][study_uuid] = study_data

        return ret