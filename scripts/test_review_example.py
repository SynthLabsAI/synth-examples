"""Offline acceptance for the public example; no model calls or submissions."""
import difflib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
TASK = ROOT / "examples/review-permissions/review-permissions"
SPEC = importlib.util.spec_from_file_location("grader", TASK / "tests/grade.py")
GRADER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRADER)
IMPLEMENTATION = GRADER.load_implementation(TASK / "environment/permissions.py")


def review(admin=False, own="a", target="a"):
    return {"findings": [{"path": "permissions.py", "title": "Permission regression",
            "explanation": "The changed condition permits a forbidden download.",
            "counterexample": {"is_admin": admin, "user_org_id": own,
                              "export_org_id": target}}]}


class ReviewExampleTests(unittest.TestCase):
    def test_both_real_counterexamples(self):
        for candidate in [review(), review(True, "a", "b")]:
            self.assertEqual(GRADER.grade(candidate, IMPLEMENTATION)["reward"], 1)

    def test_authorized_and_denied_inputs_are_not_bugs(self):
        for candidate in [review(True), review(False, "a", "b")]:
            self.assertEqual(GRADER.grade(candidate, IMPLEMENTATION)["reward"], 0)

    def test_empty_duplicate_malformed_and_wrong_path(self):
        candidates = [None, [], {}, {"findings": []}, {"findings": [None]},
                      {"findings": review()["findings"] * 2}]
        for field, value in [("path", "other.py"), ("title", ""),
                             ("explanation", None), ("counterexample", {})]:
            candidate = review()
            candidate["findings"][0][field] = value
            candidates.append(candidate)
        for candidate in candidates:
            self.assertEqual(GRADER.grade(candidate, IMPLEMENTATION)["reward"], 0)

    def test_boolean_strings_rejected(self):
        self.assertEqual(GRADER.grade(review("false"), IMPLEMENTATION)["reward"], 0)

    def test_fixed_implementation_rejects_counterexample(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "fixed.py"
            source = (TASK / "environment/permissions.py").read_text()
            path.write_text(source.replace("user.is_admin or", "user.is_admin and"))
            fixed = GRADER.load_implementation(path)
            self.assertEqual(GRADER.grade(review(), fixed)["reward"], 0)

    def test_instruction_format_example_does_not_supply_answer(self):
        source = (TASK / "instruction.md").read_text()
        sample = json.loads(source.split("```json\n")[1].split("```")[0])
        self.assertEqual(GRADER.grade(sample, IMPLEMENTATION)["reward"], 0)

    def test_reward_file_and_missing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)
            for body in [json.dumps(review()), "not-json", None]:
                candidate = path / "review.json"
                if body is None:
                    candidate.unlink(missing_ok=True)
                else:
                    candidate.write_text(body)
                result = subprocess.run([sys.executable, "-B", str(TASK / "tests/grade.py"),
                    "--review", str(candidate), "--reward", str(path / "reward.json"),
                    "--implementation", str(TASK / "environment/permissions.py")],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads((path / "reward.json").read_text())
                self.assertEqual(set(payload), {"reward"})
                self.assertIn("rationale", json.loads((path / "assessment.json").read_text()))
                reward = payload["reward"]
                self.assertEqual(reward, 1 if body and body.startswith("{") else 0)

    def test_actor_image_does_not_copy_verifier(self):
        dockerfile = (TASK / "environment/Dockerfile").read_text()
        self.assertNotIn("COPY .", dockerfile)
        self.assertIn("COPY permissions.py POLICY.md change.diff /app/", dockerfile)
        self.assertNotIn("tests/", dockerfile)

    def test_image_supports_setup_but_actor_remains_unprivileged(self):
        dockerfile = (TASK / "environment/Dockerfile").read_text()
        self.assertFalse(any(line.startswith("USER ") for line in dockerfile.splitlines()))
        self.assertIn("ca-certificates curl git", dockerfile)
        self.assertIn("@sha256:", dockerfile)
        self.assertIn('user = "reviewer"', (TASK / "task.toml").read_text())

    def test_diff_matches_the_source_change_exactly(self):
        after = (TASK / "environment/permissions.py").read_text()
        before = after.replace("user.is_admin or", "user.is_admin and")
        expected = "".join(difflib.unified_diff(before.splitlines(keepends=True),
            after.splitlines(keepends=True), fromfile="a/permissions.py", tofile="b/permissions.py"))
        self.assertEqual((TASK / "environment/change.diff").read_text(), expected)


if __name__ == "__main__":
    unittest.main()
