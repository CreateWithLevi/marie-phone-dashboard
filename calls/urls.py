from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"calls", views.CallViewSet)
router.register(r"playbooks", views.PlaybookViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/stats/", views.dashboard_stats, name="dashboard-stats"),
    path("evaluation/", views.evaluation_report, name="evaluation-report"),
]
