from rest_framework.routers import DefaultRouter
from .views import HouseholdViewSet

router = DefaultRouter()
router.register(r"", HouseholdViewSet, basename="household")

urlpatterns = router.urls
