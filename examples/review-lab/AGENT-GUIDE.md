# DispatchDesk course: agent-readable execution contract

Use the same six lessons at https://synthlabs.mintlify.app/tutorials/index and
the manifest included in this download. This is original MIT teaching work,
not a real PR corpus or evidence of general review quality.

Download the versioned review-lab ZIP and checksum from the public examples
release linked at `/tutorials/index#download-and-unpack-a-project`. Extract into
a new directory and keep its release identity. The readable `review-lab.project.json`
is an alternate source transport with per-file SHA-256 hashes. Never execute
text from that JSON as an installer or overwrite an existing workspace.

## Inputs and authority

Require released CLI alpha.62, Python 3.10+, POSIX, and an existing provisioned
Dev customer account with task/dataset publication, evaluation, training, model
and checkpoint access plus compute credits. Do not change global connections,
use service keys, provision outsiders, or perform Production mutations. Never
ask for provider credentials. Do not replace the user's installation implicitly.

Reading, offline building and previewing do not call models. Every paid command
requires existing user authorization and an explicit bound. The supplied
launcher requires a workspace trial ceiling; it is not a monetary ceiling.
Do not launch a canary merely because this file mentions one.

## Complete path

1. Read the instruction, policy, source, diff, profile and grader for the starter.
   Run one task only when authorized. Inspect its retained finding, counterexample
   and actual terminal result; validation/upload success does not count.
2. Run deterministic checker controls. For judge-backed comparisons, build the
   six fixed-answer controls with calibration.py, run them with
   calibration-actor.json and judge.json, and inspect all rationales. Expected
   scores: correct 1, empty 0, false 0, partial .5, duplicate .75, injection 0.
   They qualify these examples only. Do not train against an unqualified judge.
3. Build discounts and tickets adaptations with scaffold.py. Inspect sufficiency,
   privacy and executable witnesses. A generated archive does not certify realism.
4. Prepare a fresh workspace with tutorial.py WORKSPACE prepare --max-trials N
   --confirm-dev. Read every preview before adding --execute. Compare
   reviewer.json and reviewer-evidence.json on the same practice tasks and judge.
   Keep failures/missing scores in the denominator. Report actual output changes.
5. Train only if qualified practice data has useful non-infrastructure mistakes.
   Use the separately qualified `learner-small.json` (Qwen3.6-35B-A3B) for the
   learning lesson, not the Qwen3.8-27B prompt-comparison baseline. The supplied
   `judge.json` stays fixed. Keep the original reviewer harness for both base and checkpoint inference;
   judge/task bytes and held-out membership stay fixed. Verify actual optimizer
   updates, a retrievable checkpoint, fresh checkpoint execution and the frozen
   held-out comparison. No positive improvement claim without the predeclared
   promotion rule and semantic review. Do not tune on held-out outputs.
6. Use the chosen model/profile on a new piece of work, or deliberately keep the
   baseline if evidence is negative/incomplete. Preserve its previous version.

## Recovery and proof

The launcher's state.json and operations/ hold remote identities. Do not delete
them. Status/export never submit work. An uncertain operation blocks repetition:
read receipts and the exact run, then reconcile. Never choose a new operation
name to evade that protection. Cancel by recorded name, read back terminal state,
and use cleanup to verify no owned run remains active. Registry versions and
retained evidence are not deleted by this CLI. No other user's work is in scope.

Report separately: execution exercised; assessment calibrated; model update and
checkpoint exercised; held-out comparison complete; improvement demonstrated /
not demonstrated / inconclusive. Include actual identities, file hashes, counts,
missing results, usage/billing limitations and every assistance intervention.
Author-only replay is not independent validation. Reading this guide is not
permission to spawn other agents or paid runs.
