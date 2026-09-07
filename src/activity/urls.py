from rest_framework.routers import DefaultRouter
from activity.views import ActivityLogViewSet

router = DefaultRouter()
router.register(r"", ActivityLogViewSet, basename="activity")

urlpatterns = router.urls
