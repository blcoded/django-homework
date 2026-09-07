from rest_framework.routers import DefaultRouter
from .views import ChoreViewSet

router = DefaultRouter()
router.register(r"", ChoreViewSet, basename="chore")

urlpatterns = router.urls
