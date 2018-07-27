from django.conf.urls import url

from . import views


app_name = 'irodsbackend'

urlpatterns = [
    url(
        regex=r'^stats/(?P<project>[0-9a-f-]+)\?path=(?P<path>[\w\-_/@]+)$',
        view=views.IrodsStatisticsGetAPIView.as_view(),
        name='stats',
    ),
    url(
        regex=r'^stats\?path=(?P<path>[\w\-_/@]+)$',
        view=views.IrodsStatisticsGetAPIView.as_view(),
        name='stats',
    ),
]
