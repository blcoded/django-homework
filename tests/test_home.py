import pytest
from django.test import Client, TestCase
from django.urls import reverse


class HomeViewTestCase(TestCase):
    """Test cases for the home and health check views."""

    def setUp(self):
        self.client = Client()

    def test_home_page_returns_ok(self):
        """Smoke test verifying the root endpoint returns 200 OK and expected payload."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["name"], "Shared Household Chores API")

    def test_health_check_returns_ok(self):
        """Smoke test verifying the health check endpoint returns 200 OK."""
        response = self.client.get(reverse("health-check"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")


@pytest.mark.django_db
def test_home_endpoint_pytest(client):
    """Pytest fixture-style test verifying the home endpoint."""
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert response.json()["status"] == "online"
