from rest_framework.routers import DefaultRouter
from .views import (
    ChoreOccurrenceViewSet,
    ChoreSuggestionViewSet,
    ChoreSwapRequestViewSet,
    ChoreViewSet,
)

router = DefaultRouter()
router.register(r"suggestions", ChoreSuggestionViewSet, basename="chore-suggestion")
router.register(r"occurrences", ChoreOccurrenceViewSet, basename="chore-occurrence")
router.register(r"swaps", ChoreSwapRequestViewSet, basename="chore-swap")
router.register(r"", ChoreViewSet, basename="chore")

urlpatterns = router.urls
