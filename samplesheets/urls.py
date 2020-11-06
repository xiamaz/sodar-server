from django.conf.urls import url

import samplesheets.views_ajax
import samplesheets.views_api
import samplesheets.views_taskflow
from samplesheets import views


app_name = 'samplesheets'

# UI views
urls_ui = [
    url(
        regex=r'^(?P<project>[0-9a-f-]+)$',
        view=views.ProjectSheetsView.as_view(),
        name='project_sheets',
    ),
    url(
        regex=r'^import/(?P<project>[0-9a-f-]+)$',
        view=views.SampleSheetImportView.as_view(),
        name='import',
    ),
    url(
        regex=r'^export/excel/study/(?P<study>[0-9a-f-]+)$',
        view=views.SampleSheetExcelExportView.as_view(),
        name='export_excel',
    ),
    url(
        regex=r'^export/excel/assay/(?P<assay>[0-9a-f-]+)$',
        view=views.SampleSheetExcelExportView.as_view(),
        name='export_excel',
    ),
    url(
        regex=r'^export/isa/(?P<project>[0-9a-f-]+)$',
        view=views.SampleSheetISAExportView.as_view(),
        name='export_isa',
    ),
    url(
        regex=r'^export/version/(?P<isatab>[0-9a-f-]+)$',
        view=views.SampleSheetISAExportView.as_view(),
        name='export_isa',
    ),
    url(
        regex=r'^collections/(?P<project>[0-9a-f-]+)$',
        view=views.IrodsCollectionsView.as_view(),
        name='collections',
    ),
    url(
        regex=r'^delete/(?P<project>[0-9a-f-]+)$',
        view=views.SampleSheetDeleteView.as_view(),
        name='delete',
    ),
    url(
        regex=r'^cache/update/(?P<project>[0-9a-f-]+)$',
        view=views.SampleSheetCacheUpdateView.as_view(),
        name='cache_update',
    ),
    url(
        regex=r'^versions/(?P<project>[0-9a-f-]+)$',
        view=views.SampleSheetVersionListView.as_view(),
        name='versions',
    ),
    url(
        regex=r'^version/restore/(?P<isatab>[0-9a-f-]+)$',
        view=views.SampleSheetVersionRestoreView.as_view(),
        name='version_restore',
    ),
    url(
        regex=r'^version/delete/(?P<isatab>[0-9a-f-]+)$',
        view=views.SampleSheetVersionDeleteView.as_view(),
        name='version_delete',
    ),
]

# REST API views
urls_api = [
    url(
        regex=r'^api/investigation/retrieve/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_api.InvestigationRetrieveAPIView.as_view(),
        name='api_investigation_retrieve',
    ),
    url(
        regex=r'^api/irods/collections/create/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_api.IrodsCollsCreateAPIView.as_view(),
        name='api_irods_colls_create',
    ),
    url(
        regex=r'^api/import/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_api.SampleSheetImportAPIView.as_view(),
        name='api_import',
    ),
    url(
        regex=r'^api/export/zip/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_api.SampleSheetISAExportAPIView.as_view(),
        name='api_export_zip',
    ),
    url(
        regex=r'^api/export/json/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_api.SampleSheetISAExportAPIView.as_view(),
        name='api_export_json',
    ),
    url(
        regex=r'^api/file/exists$',
        view=samplesheets.views_api.SampleDataFileExistsAPIView.as_view(),
        name='api_file_exists',
    ),
    url(
        regex=r'^api/remote/get/(?P<project>[0-9a-f-]+)/(?P<secret>[\w\-]+)$',
        view=samplesheets.views_api.RemoteSheetGetAPIView.as_view(),
        name='api_remote_get',
    ),
]

# Ajax API views
urls_ajax = [
    # TODO: Rename views and URL patterns
    url(
        regex=r'^ajax/context/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetContextAjaxView.as_view(),
        name='ajax_context',
    ),
    url(
        regex=r'^ajax/study/tables/(?P<study>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetStudyTablesAjaxView.as_view(),
        name='ajax_study_tables',
    ),
    url(
        regex=r'^ajax/study/links/(?P<study>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetStudyLinksAjaxView.as_view(),
        name='ajax_study_links',
    ),
    url(
        regex=r'^ajax/warnings/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetWarningsAjaxView.as_view(),
        name='ajax_warnings',
    ),
    url(
        regex=r'^ajax/edit/cell/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SheetCellEditAjaxView.as_view(),
        name='ajax_edit_cell',
    ),
    url(
        regex=r'^ajax/edit/row/insert/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SheetRowInsertAjaxView.as_view(),
        name='ajax_edit_row_insert',
    ),
    url(
        regex=r'^ajax/edit/row/delete/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SheetRowDeleteAjaxView.as_view(),
        name='ajax_edit_row_delete',
    ),
    url(
        regex=r'^ajax/edit/finish/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetEditFinishAjaxView.as_view(),
        name='ajax_edit_finish',
    ),
    url(
        regex=r'^ajax/manage/(?P<project>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.SampleSheetManageAjaxView.as_view(),
        name='ajax_manage',
    ),
    url(
        regex=r'^ajax/display/update/(?P<study>[0-9a-f-]+)$',
        view=samplesheets.views_ajax.StudyDisplayConfigAjaxView.as_view(),
        name='ajax_display_update',
    ),
]

# Taskflow API views
urls_taskflow = [
    url(
        regex=r'^taskflow/dirs/get$',
        view=samplesheets.views_taskflow.TaskflowCollStatusGetAPIView.as_view(),
        name='taskflow_sheet_colls_get',
    ),
    url(
        regex=r'^taskflow/dirs/set$',
        view=samplesheets.views_taskflow.TaskflowCollStatusSetAPIView.as_view(),
        name='taskflow_sheet_colls_set',
    ),
    url(
        regex=r'^taskflow/delete$',
        view=samplesheets.views_taskflow.TaskflowSheetDeleteAPIView.as_view(),
        name='taskflow_sheet_delete',
    ),
]

urlpatterns = urls_ui + urls_api + urls_ajax + urls_taskflow
