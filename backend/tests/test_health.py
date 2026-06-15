"""
Module 1 — Health Check Tests.

Tests the /health/ endpoint introduced in Module 1.
These are integration tests using Django's test client.
"""

import json

from django.test import TestCase
from django.urls import reverse


class HealthCheckTestCase(TestCase):
    """Tests for the /health/ endpoint."""

    def setUp(self):
        self.url = "/health/"

    def test_health_check_returns_200(self):
        """Health endpoint must return HTTP 200 OK."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_json(self):
        """Health endpoint must return valid JSON with Content-Type application/json."""
        response = self.client.get(self.url)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_check_response_body(self):
        """Health endpoint body must contain status='ok' and service field."""
        response = self.client.get(self.url)
        data = json.loads(response.content)

        self.assertIn("status", data)
        self.assertEqual(data["status"], "ok")
        self.assertIn("service", data)
        self.assertEqual(data["service"], "splitwise-clone-api")
        self.assertIn("version", data)

    def test_health_check_allows_get_without_auth(self):
        """Health endpoint must not require authentication."""
        # No Authorization header set — should still return 200
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_health_check_post_not_allowed(self):
        """Health endpoint only allows GET, not POST."""
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 405)
