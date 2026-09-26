# Synth examples

Complete, inspectable examples for building, running, evaluating and improving
agents with the [Synth CLI](https://synthlabs.mintlify.app/).

Synth is not limited to coding or GitHub. An agent profile describes a model and
its execution recipe; a task supplies the work and environment; an assessment
defines success. A support case, evidence-grounded document analysis or research
task can use the same structure, with suitable tools, context and assessment.
Those are application ideas, not bundled integrations. The first worked example
here is code review because its source, output and counterexample are inspectable.

## Start here

Read [Get a useful review](https://synthlabs.mintlify.app/tutorials/first-review)
for a real recorded result without an account or model spending.

- `examples/review-permissions/`: the complete one-task starter, reviewer profile
  and evaluation plan. Upload only its nested `review-permissions/` task folder.
- `examples/review-lab/`: the connected DispatchDesk course with task generation,
  profiles, assessment controls, adaptations, bounded launch and reporting tools.
- Tagged releases provide ordinary ZIP files and SHA-256 checksums. Each archive
  expands to the corresponding example files; extract into a new directory.

Live execution is qualified with CLI **0.0.1-alpha.62**, Python 3.10+, and an
**existing provisioned Dev account** with model access, task/dataset publication,
execution/training permissions and compute credits. Public signup does not
automatically grant these permissions. No provider credentials are distributed
here. Reading and building the packages do not call models; execution spends
compute and requires your authorization.

The examples are original MIT-licensed teaching projects, not historical customer
work. A completed run or trained checkpoint is not evidence that an agent improved.
Inspect actual work and fresh, fixed comparisons. Do not treat a teaching score
as domain certification or authorization for autonomous safety-critical decisions.

## Rebuild downloads without paid work

```bash
python3 -B scripts/build.py
python3 -B scripts/test_distribution.py
python3 -B scripts/test_review_lab.py
python3 -B scripts/test_tutorial_launcher.py
python3 -B scripts/test_tutorial_report.py
```

Archives and checksums are generated in `dist/`. Source files, deterministic task
generation and the per-file manifest remain inspectable. These commands do not
authenticate, publish Registry resources, launch agents or train models.

Changes use reviewed pull requests. Release assets are versioned and must not be
replaced in place; fixes receive a new release. Keep task/profile bytes and
reference results tied to the versions actually exercised.
