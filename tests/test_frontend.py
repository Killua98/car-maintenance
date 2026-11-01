import re
import unittest
from pathlib import Path

import frontend
from backend.main import app, read_root

from . import API_URLS


class FrontendTests(unittest.TestCase):
    def test_read_root_returns_index_html(self) -> None:
        html = read_root()
        expected_html = (Path(frontend.__file__).parent / "index.html").read_text(
            encoding="utf-8"
        )
        match = re.search(r'<script src="/static/js/api\.js\?v=([^"]+)"', html)
        self.assertIsNotNone(match, "Tag script non trovato nell'HTML")
        assert match is not None
        version = match.group(1)

        self.assertEqual(html, expected_html.replace("__VERSION__", version))

    def test_login_and_superuser_user_management_screens_are_available(self) -> None:
        html = read_root()

        self.assertIn('id="show-registration"', html)
        self.assertIn('id="registration-form"', html)
        self.assertIn('id="profile-button"', html)
        self.assertIn('id="profile-panel"', html)
        self.assertIn('id="profile-form"', html)
        self.assertIn('id="password-form"', html)
        self.assertIn('id="admin-user-management"', html)
        self.assertIn('id="admin-create-user-form"', html)
        self.assertIn('id="user-table-body"', html)

    def test_mileage_history_has_add_record_button(self) -> None:
        html = read_root()

        self.assertIn('id="add-mileage-record-button"', html)
        self.assertIn('onclick="openMileageModal()"', html)
        self.assertIn('id="mileage-view-toggle"', html)

    def test_api_registry_is_loaded_before_application(self) -> None:
        html = read_root()

        registry_script = html.index("/static/js/api.js?v=")
        application_script = html.index("/static/js/app.js?v=")

        self.assertLess(registry_script, application_script)

        # 1. Eseguiamo le ricerche salvandole in variabili separate
        api_match = re.search(r'/static/js/api\.js\?v=([^"]+)', html)
        app_match = re.search(r'/static/js/app\.js\?v=([^"]+)', html)

        # 2. Verifichiamo che entrambe le corrispondenze esistano
        self.assertIsNotNone(api_match, "Script dell'API non trovato nell'HTML")
        self.assertIsNotNone(
            app_match, "Script dell'applicazione non trovato nell'HTML"
        )
        assert api_match and app_match is not None
        # 3. Confrontiamo le versioni estratte in sicurezza
        self.assertEqual(api_match.group(1), app_match.group(1))

    def test_backend_registers_api_registry_paths(self) -> None:
        paths = app.openapi()["paths"]
        expected_paths = {
            API_URLS["login"],
            f"{API_URLS['users']}/check-setup",
            f"{API_URLS['users']}/",
            f"{API_URLS['cars']}/",
            f"{API_URLS['maintenance']}/{{maintenance_id}}",
            f"{API_URLS['mileage']}/{{mileage_id}}",
        }

        self.assertTrue(expected_paths.issubset(paths))
