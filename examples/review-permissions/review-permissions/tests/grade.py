"""Assess executable counterexamples, not the semantic quality of review prose."""
import argparse
import importlib.util
import json
import pathlib
import sys


def load_implementation(path):
    spec = importlib.util.spec_from_file_location("review_example", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def grade(review, implementation):
    findings = review.get("findings") if isinstance(review, dict) else None
    if not isinstance(findings, list):
        return {"reward": 0.0, "rationale": "Expected a findings array."}
    if len(findings) != 1:
        return {"reward": 0.0, "rationale": "Report the single root cause once, or no finding."}
    finding = findings[0]
    if not isinstance(finding, dict) or finding.get("path") != "permissions.py":
        return {"reward": 0.0, "rationale": "The finding must identify permissions.py."}
    if any(not isinstance(finding.get(key), str) or not finding[key].strip()
           for key in ("title", "explanation")):
        return {"reward": 0.0, "rationale": "Provide a title and explanation."}
    case = finding.get("counterexample")
    if not isinstance(case, dict) or type(case.get("is_admin")) is not bool:
        return {"reward": 0.0, "rationale": "Provide a counterexample with a JSON boolean is_admin."}
    if any(not isinstance(case.get(key), str) or not case[key]
           for key in ("user_org_id", "export_org_id")):
        return {"reward": 0.0, "rationale": "Counterexample organization IDs must be nonempty strings."}
    user = implementation.User(case["is_admin"], case["user_org_id"])
    export = implementation.Export(case["export_org_id"])
    policy_allows = user.is_admin and user.org_id == export.org_id
    implementation_allows = implementation.can_download(user, export)
    try:
        leaked = implementation.download_export(user, export) == export.contents
    except PermissionError:
        leaked = False
    valid = implementation_allows is True and policy_allows is False and leaked
    return {
        "reward": 1.0 if valid else 0.0,
        "rationale": ("The supplied input demonstrates a forbidden download." if valid
                      else "The supplied input does not demonstrate the regression."),
        "assessment_scope": "executable counterexample; prose quality is not independently scored",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True)
    parser.add_argument("--reward", required=True)
    parser.add_argument("--implementation", default="/app/permissions.py")
    args = parser.parse_args()
    implementation = load_implementation(args.implementation)
    try:
        review = json.loads(pathlib.Path(args.review).read_text())
    except (OSError, ValueError):
        result = {"reward": 0.0, "rationale": "The review file is missing or is not valid JSON."}
    else:
        result = grade(review, implementation)
    destination = pathlib.Path(args.reward)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Harbor's executable-verifier result is a numeric mapping. Keep prose in
    # a separate retained artifact; the model-judge adapter is a distinct API.
    destination.with_name("assessment.json").write_text(json.dumps(result) + "\n")
    destination.write_text(json.dumps({"reward": result["reward"]}) + "\n")


if __name__ == "__main__":
    main()
