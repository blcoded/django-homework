from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()


class UserAuthenticationTestCase(TestCase):
    """Automated tests for user registration, authentication, tokens, and profiles."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("auth-register")
        self.login_url = reverse("auth-login")
        self.logout_url = reverse("auth-logout")
        self.profile_url = reverse("auth-profile")

        self.user_data = {
            "email": "roommate@example.com",
            "password": "SecurePassword123!",
            "display_name": "Roomie Sam",
        }

    def test_registration_success(self):
        """User can register with valid credentials and receive token and profile."""
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("token", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "roommate@example.com")
        self.assertEqual(data["user"]["display_name"], "Roomie Sam")

        # Assert user persisted with password hashed
        user = User.objects.get(email="roommate@example.com")
        self.assertTrue(user.check_password("SecurePassword123!"))
        self.assertEqual(Token.objects.filter(user=user).count(), 1)

    def test_duplicate_email_rejection(self):
        """Registering with an already registered email (case-insensitive) is rejected."""
        self.client.post(self.register_url, self.user_data, format="json")

        # Attempt duplicate with mixed case
        duplicate_data = {
            "email": "ROOMMATE@EXAMPLE.COM",
            "password": "AnotherPassword456!",
            "display_name": "Duplicate Sam",
        }
        response = self.client.post(self.register_url, duplicate_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    def test_registration_invalid_password(self):
        """Passwords shorter than 8 characters are rejected."""
        invalid_data = {
            "email": "shortpass@example.com",
            "password": "short",
            "display_name": "Short Pass",
        }
        response = self.client.post(self.register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json())

    def test_registration_invalid_email(self):
        """Malformed emails are rejected."""
        invalid_data = {
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "display_name": "Invalid Email",
        }
        response = self.client.post(self.register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    def test_login_success(self):
        """User can log in with valid credentials and receive token and session."""
        User.objects.create_user(**self.user_data)

        login_data = {
            "email": "roommate@example.com",
            "password": "SecurePassword123!",
        }
        response = self.client.post(self.login_url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], "roommate@example.com")

    def test_login_case_insensitive(self):
        """Login works with case-insensitive email."""
        User.objects.create_user(**self.user_data)

        login_data = {
            "email": "ROOMMATE@example.COM",
            "password": "SecurePassword123!",
        }
        response = self.client.post(self.login_url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_invalid_password(self):
        """Login with wrong password fails."""
        User.objects.create_user(**self.user_data)

        login_data = {
            "email": "roommate@example.com",
            "password": "WrongPassword!",
        }
        response = self.client.post(self.login_url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_user(self):
        """Login with unknown email fails."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!",
        }
        response = self.client.post(self.login_url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_retrieval_authenticated_with_token(self):
        """Authenticated user can retrieve profile via token."""
        user = User.objects.create_user(**self.user_data)
        token = Token.objects.create(user=user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["email"], user.email)
        self.assertEqual(data["display_name"], "Roomie Sam")

    def test_profile_retrieval_unauthenticated(self):
        """Unauthenticated request to profile endpoint is denied with 401."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_update(self):
        """Authenticated user can update their display name."""
        user = User.objects.create_user(**self.user_data)
        token = Token.objects.create(user=user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.patch(
            self.profile_url, {"display_name": "Sam Updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["display_name"], "Sam Updated")

        user.refresh_from_db()
        self.assertEqual(user.display_name, "Sam Updated")

    def test_logout_revokes_token(self):
        """Logout invalidates user token."""
        user = User.objects.create_user(**self.user_data)
        token = Token.objects.create(user=user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Token should be deleted
        self.assertFalse(Token.objects.filter(key=token.key).exists())

        # Attempting to access profile with revoked token returns 401
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
