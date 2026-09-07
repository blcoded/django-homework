from rest_framework.routers import DefaultRouter
from .views import HouseholdViewSet, AbsenceRequestViewSet

router = DefaultRouter()
router.register(r"absences", AbsenceRequestViewSet, basename="absence-request")
router.register(r"", HouseholdViewSet, basename="household")

urlpatterns = router.urls
