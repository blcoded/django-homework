from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class SmokeTestCase(SimpleTestCase):
    """Basic smoke tests verifying configuration and routing."""

    def test_settings_configured(self):
        """Verify Django settings are properly loaded."""
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertEqual(settings.ROOT_URLCONF, "django_homework.urls")
        self.assertIn("rest_framework", settings.INSTALLED_APPS)
        self.assertIn("corsheaders", settings.INSTALLED_APPS)
        self.assertIn("django_homework.apps.DjangoHomeworkConfig", settings.INSTALLED_APPS)


    def test_health_check_endpoint(self):
        """Verify health check endpoint returns 200 OK and expected JSON payload."""
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "message": "Shared Household Chores API"},
        )


class DatabaseSmokeTestCase(TestCase):
    """Smoke test asserting database setup and connectivity through the test runner."""

    def test_database_connection(self):
        """Verify the test database is accessible and can execute a query."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        self.assertEqual(row[0], 1)
