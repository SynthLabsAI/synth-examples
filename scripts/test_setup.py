"""Read-only local setup checks and first-result work bounds; no live CLI calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("setup_check", ROOT/"examples/review-permissions/check_setup.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class SetupTests(unittest.TestCase):
    def test_missing_cli_has_installation_guidance(self):
        with patch.object(CHECK.subprocess, "run", side_effect=FileNotFoundError("missing")):
            with self.assertRaisesRegex(ValueError, "Synth CLI.*not found.*https://synthlabs.mintlify.app/getting-started/install"):
                CHECK.invoke(["version"])

    def run_check(self, confirmed=True, version=CHECK.EXPECTED, **status):
        calls = []
        auth = {"request_authenticated": True, "service_key_active": False,
                "api_base_url": "https://provisioned.example.test"}
        auth.update(status)
        def runner(args):
            calls.append(args)
            self.assertIn(args[0], ("version", "status", "agent"))
            if args[0] == "version":
                return version
            if args[0] == "status":
                return json.dumps(auth)
            self.assertEqual(args[:2], ["agent", "validate"])
            return "valid"
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/"reviewer.json").write_text("{}")
            result = CHECK.check(folder, confirmed, runner)
        self.assertEqual(len(calls), 3)
        return result

    def test_ready_is_not_live_permission_or_model_proof(self):
        result = self.run_check()
        self.assertEqual(result["local_prerequisites"], "passed")
        self.assertEqual(result["server_admission"], "not tested")
        self.assertEqual(result["model_availability"], "not tested")
        self.assertFalse(result["paid_work_submitted"])
        self.assertNotIn("api_base_url", result)

    def test_sign_in_works_without_environment_confirmation(self):
        self.assertEqual(self.run_check(confirmed=False)["local_prerequisites"], "passed")

    def test_default_customer_endpoint_is_accepted(self):
        for endpoint in (CHECK.PRODUCTION, CHECK.PRODUCTION+'/', CHECK.PRODUCTION.upper(),
                         CHECK.PRODUCTION+':443', CHECK.PRODUCTION+'./'):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.run_check(api_base_url=endpoint)["local_prerequisites"], "passed")

    def test_fail_closed_for_wrong_context_auth_release(self):
        for args in ({"version": "synth 0.0.1-alpha.51"},
                     {"request_authenticated": False}, {"service_key_active": True},
                     {"api_base_url": "http://localhost"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.run_check(**args)

    def test_missing_or_symlinked_profile_rejected(self):
        def runner(args):
            return CHECK.EXPECTED if args == ["version"] else json.dumps({
                "request_authenticated": True, "api_base_url": "https://provisioned.example.test"})
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for symlink in (False, True):
                if symlink:
                    (folder/"reviewer.json").symlink_to(folder/"absent")
                with self.assertRaises(ValueError):
                    CHECK.check(folder, True, runner)

    def test_credentials_and_malformed_urls_rejected(self):
        for endpoint in ('https://user@sprites-gateway.api.synthlabs.ai',
                         'https://provisioned.example.test?token=not-a-real-secret',
                         'https://', 'https://provisioned.example.test:bad',
                         'https://provisioned.example.test/#fragment'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                self.run_check(api_base_url=endpoint)

    def test_project_copies_are_identical(self):
        self.assertEqual((ROOT/"examples/review-permissions/check_setup.py").read_bytes(),
                         (ROOT/"examples/review-lab/check_setup.py").read_bytes())

    def test_first_result_is_exactly_one_trial(self):
        self.assertEqual(json.loads((ROOT/"examples/review-permissions/eval-plan.json").read_text()),
                         {"trials_per_task": 1})


if __name__ == "__main__":
    unittest.main()
