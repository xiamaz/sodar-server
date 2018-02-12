"""Utilities for the samplesheets app"""

import datetime as dt
import logging

from .models import Investigation, Study, Assay, GenericMaterial, Protocol, \
    Process


logger = logging.getLogger(__name__)


# Importing --------------------------------------------------------------------


def import_isa_json(json_data, file_name, project):
    """
    Import ISA investigation from JSON data and create relevant objects in
    the Django database.
    :param json_data: JSON data (dict)
    :param file_name: Name of the investigation file
    :param project: Project object
    :return: Investigation object
    """

    def import_material(material, parent, item_type):
        """
        Create a material object in Django database.
        :param material: Material dictionary from ISA JSON
        :param parent: Parent database object (Assay or Study)
        :param item_type: Type of GenericMaterial
        :return: GenericMaterial object
        """

        # Common values
        values = {
            'api_id': material['@id'],
            'item_type': item_type,
            'name': material['name'],
            'characteristics': (material['characteristics'] if
                                item_type != 'DATA' else dict())}

        if type(parent) == Study:
            values['study'] = parent

        elif type(parent) == Assay:
            values['assay'] = parent

        if 'type' in material:
            values['material_type'] = material['type']

        if 'characteristics' in material:
            values['characteristics'] = material['characteristics']

        if 'factorValues' in material:
            # HACK: Workaround for factor values imported twice in ISA JSON
            imported_ids = []
            factor_values = []

            for fv in material['factorValues']:
                if fv['category']['@id'] not in imported_ids:
                    factor_values.append(fv)
                    imported_ids.append(fv['category']['@id'])

            values['factor_values'] = factor_values

        material_obj = GenericMaterial(**values)
        material_obj.save()
        logging.debug('Added material "{}" ({})'.format(
            material_obj.name, item_type))

        return material_obj

    def import_processes(sequence, parent):
        """
        Create processes of a process sequence in the database.
        :param sequence: Process sequence of a study or an assay
        :param parent: Parent study or assay
        :return: Process object (first process)
        """
        first_process = None
        prev_process = None
        study = parent if type(parent) == Study else parent.study

        for p in sequence:
            protocol = Protocol.objects.get(
                study=study,
                api_id=p['executesProtocol']['@id'])

            values = {
                'api_id': p['@id'],
                'protocol': protocol,
                'assay': parent if type(parent) == Assay else None,
                'study': parent if type(parent) == Study else None,
                'previous_process': prev_process,
                'parameter_values': p['parameterValues'],
                'performer': p['performer'],
                'perform_date': (
                    dt.datetime.strptime(p['date'], '%Y-%m-%d').date() if
                    p['date'] else None),
                'comments': p['comments']}

            process = Process(**values)
            process.save()
            logging.debug('Added process "{}" to "{}"'.format(
                process.api_id, parent.api_id))

            if not first_process:
                first_process = process

            # Link inputs
            for i in p['inputs']:
                input_material = GenericMaterial.objects.find_child(
                    parent, i['@id'])

                process.inputs.add(input_material)
                logging.debug('Linked input material "{}"'.format(
                    input_material.api_id))

            # Link outputs
            for o in p['outputs']:
                output_material = GenericMaterial.objects.find_child(
                    parent, o['@id'])

                process.outputs.add(output_material)
                logging.debug('Linked output material "{}"'.format(
                    output_material.api_id))

            prev_process = process

        return first_process

    logging.debug('Importing investigation from JSON dict..')

    # Create investigation
    values = {
        'project': project,
        'identifier': json_data['identifier'],
        'title': (json_data['title'] or project.title),
        'description': (json_data['description'] or
                        project.description),
        'file_name': file_name,
        'ontology_source_refs': json_data['ontologySourceReferences'],
        'comments': json_data['comments']}

    investigation = Investigation(**values)
    investigation.save()
    logging.debug('Created investigation "{}"'.format(investigation.title))

    # Create studies
    for s in json_data['studies']:
        values = {
            'api_id': s['@id'] if hasattr(s, '@id') else None,
            'identifier': s['identifier'],
            'file_name': s['filename'],
            'investigation': investigation,
            'title': s['title'],
            'study_design': s['studyDesignDescriptors'],
            'factors': s['factors'],
            'characteristic_cat': s['characteristicCategories'],
            'unit_cat': s['unitCategories'],
            'comments': s['comments']}

        study = Study(**values)
        study.save()
        logging.debug('Added study "{}"'.format(study.api_id))

        # Create protocols
        for p in s['protocols']:
            values = {
                'api_id': p['@id'],
                'name': p['name'],
                'study': study,
                'protocol_type': p['protocolType'],
                'description': p['description'],
                'uri': p['uri'],
                'version': p['version'],
                'parameters': p['parameters'],
                'components': p['components']}

            protocol = Protocol(**values)
            protocol.save()
            logging.debug('Added protocol "{}" in study "{}"'.format(
                protocol.api_id, study.api_id))

        # Create study sources
        for m in s['materials']['sources']:
            import_material(m, parent=study, item_type='SOURCE')

        # Create study samples
        for m in s['materials']['samples']:
            import_material(m, parent=study, item_type='SAMPLE')

        # Create other study materials
        for m in s['materials']['otherMaterials']:
            import_material(m, parent=study, item_type='MATERIAL')

        # Create study processes
        import_processes(s['processSequence'], parent=study)

        # Create assays
        for a in s['assays']:
            values = {
                'api_id': a['@id'] if hasattr(a, '@id') else None,
                'file_name': a['filename'],
                'study': study,
                'measurement_type': a['measurementType'],
                'technology_type': a['technologyType'],
                'technology_platform': a['technologyPlatform'],
                'characteristic_cat': a['characteristicCategories'],
                'unit_cat': a['unitCategories'],
                'comments': a['comments'] if 'comments' in a else []}

            assay = Assay(**values)
            assay.save()
            logging.debug('Added assay "{}" in study "{}"'.format(
                assay.api_id, study.api_id))

            # Create assay data files
            for m in a['dataFiles']:
                import_material(m, parent=assay, item_type='DATA')

            # Create other assay materials
            # NOTE: Samples were already created when parsing study
            for m in a['materials']['otherMaterials']:
                import_material(m, parent=assay, item_type='MATERIAL')

            # Create assay processes
            import_processes(a['processSequence'], parent=assay)

    logging.debug('Import OK')
    return investigation


# Exporting --------------------------------------------------------------------


def export_isa_json(investigation):
    """
    Export ISA investigation into a dictionary corresponding to ISA JSON
    :param investigation: Investigation object
    :return: Dictionary
    """

    def get_reference(obj):
        """
        Return reference to an object for exporting
        :param obj: Any object inheriting BaseSampleSheet
        :return: Reference value as dict
        """
        return {'@id': obj.api_id}

    def export_materials(parent_obj, parent_data):
        """
        Export materials from a parent into output dict
        :param parent_obj: Study or Assay object
        :param parent_data: Parent study or assay in output dict
        """
        for material in parent_obj.materials.all():
            material_data = {
                '@id': material.api_id,
                'name': material.name}

            # Characteristics for all material types except data files
            if material.item_type != 'DATA':
                material_data['characteristics']: material.characteristics

            # Source
            if material.item_type == 'SOURCE':
                parent_data['materials']['sources'].append(material_data)

            # Sample
            elif material.item_type == 'SAMPLE':
                material_data['factorValues'] = material.factor_values
                parent_data['materials']['samples'].append(material_data)

            # Other materials
            elif material.item_type == 'MATERIAL':
                material_data['type'] = material.material_type
                parent_data['materials']['otherMaterials'].append(material_data)

            # Data files
            elif material.item_type == 'DATA':
                material_data['type'] = material.material_type
                parent_data['dataFiles'].append(material_data)

            logging.debug('Added material "{}" ({})'.format(
                material.name, material.item_type))

    def export_processes(parent_obj, parent_data):
        """
        Export process sequence from a parent into output dict
        :param parent_obj: Study or Assay object
        :param parent_data: Parent study or assay in output dict
        """
        process = parent_obj.get_first_process()

        while process:
            process_data = {
                '@id': process.api_id,
                'executesProtocol': get_reference(process.protocol),
                'parameterValues': process.parameter_values,
                'performer': process.performer,
                'date': str(
                    process.perform_date) if process.perform_date else '',
                'comments': process.comments,
                'inputs': [],
                'outputs': []}

            # The name string seems to be optional
            if process.name:
                process_data['name'] = process.name

            if hasattr(process, 'next_process') and process.next_process:
                process_data['nextProcess'] = get_reference(
                    process.next_process)

            if hasattr(process,
                       'previous_process') and process.previous_process:
                process_data['previousProcess'] = get_reference(
                    process.previous_process)

            for i in process.inputs.all():
                process_data['inputs'].append(get_reference(i))

            for o in process.outputs.all():
                process_data['outputs'].append(get_reference(o))

            parent_data['processSequence'].append(process_data)
            logging.debug('Added process "{}"'.format(process.name))

            if hasattr(process, 'next_process'):
                process = process.next_process

            else:
                process = None

    logging.debug('Exporting ISA data into JSON dict..')

    # Investigation properties
    ret = {
        'identifier': investigation.identifier,
        'title': investigation.title,
        'description': investigation.description,
        'filename': investigation.file_name,
        'ontologySourceReferences': investigation.ontology_source_refs,
        'comments': investigation.comments,
        'submissionDate': '',
        'publicReleaseDate': '',
        'studies': [],
        'publications': [],
        'people': []}
    logging.debug('Added investigation "{}"'.format(investigation.title))

    # Studies
    for study in investigation.studies.all():
        study_data = {
            'identifier': study.identifier,
            'filename': study.file_name,
            'title': study.title,
            'description': study.description,
            'studyDesignDescriptors': study.study_design,
            'factors': study.factors,
            'characteristicCategories': study.characteristic_cat,
            'unitCategories': study.unit_cat,
            'submissionDate': '',
            'publicReleaseDate': '',
            'comments': study.comments,
            'protocols': [],
            'materials': {
                'sources': [],
                'samples': [],
                'otherMaterials': []
            },
            'assays': [],
            'processSequence': []}

        if study.api_id:
            study_data['@id'] = study.api_id

        logging.debug('Added study "{}"'.format(study.title))

        # Protocols
        for protocol in study.protocols.all():
            protocol_data = {
                '@id': protocol.api_id,
                'name': protocol.name,
                'protocolType': protocol.protocol_type,
                'description': protocol.description,
                'uri': protocol.uri,
                'version': protocol.version,
                'parameters': protocol.parameters,
                'components': protocol.components}
            study_data['protocols'].append(protocol_data)
            logging.debug('Added protocol "{}"'.format(protocol.name))

        # Materials
        export_materials(study, study_data)

        # Processes
        export_processes(study, study_data)

        # Assays
        for assay in study.assays.all():
            assay_data = {
                'filename': assay.file_name,
                'technologyPlatform': assay.technology_platform,
                'technologyType': assay.technology_type,
                'measurementType': assay.measurement_type,
                'characteristicCategories': assay.characteristic_cat,
                'unitCategories': assay.unit_cat,
                'comments': assay.comments,
                'processSequence': [],
                'dataFiles': [],
                'materials': {
                    'samples': [],
                    'otherMaterials': []}}

            if assay.api_id:
                assay_data['@id'] = assay.api_id

            logging.debug('Added assay "{}"'.format(assay.file_name))

            # Assay materials and data files
            export_materials(assay, assay_data)

            # Assay processes
            export_processes(assay, assay_data)

            study_data['assays'].append(assay_data)

        ret['studies'].append(study_data)

    logging.debug('Export to dict OK')
    return ret
