# DispatchDesk review lab

Original MIT-licensed teaching code, not historical customer pull requests.
The exercise concerns concrete authorization, capacity, freshness, path,
pagination, deduplication and retention contracts. It does not establish general
code-review performance. The environment is separate from the agent profile.

`build.py NEW_DIRECTORY` creates 32 complete tasks: eight foundational, eight
core practice, eight held out and eight extension tasks from `curriculum.py`.
The launcher selects only the eight core practice or eight held-out tasks by
default. Every actor receives the complete small
source tree, caller, policy, change and input domain. Every assessor receives
the immutable before/after code and reference. No Git history or private source
is required. Clean and buggy siblings remain together in the same split.

The finite interface is intentional: `INPUTS.json` lists supported requests,
not expected answers. This makes the counterexample checker fully specified.
It is a teaching microbenchmark, not a substitute for representative company
tasks with their real callers, dependencies, tests and business policies.

The executable verifier checks the counterexample, not prose truth. The model
judge also assesses the explanation using the supplied frozen rubric. Judge
calibration is mandatory before training against its scores.

Do not submit training merely because the tasks upload: first measure whether
there is usable reward variation. A perfect or always-failing baseline is not
a useful learning exercise. `reviewer.json` and `reviewer-evidence.json` are a
matched Qwen3.8 prompt comparison. `learner-small.json` is the separately
qualified Qwen3.6 learning baseline; `learner.json` (Inkling) and
`reviewer-readonly.json` are retained qualification alternatives, not silently
interchangeable versions. Follow the versioned reference results and the six
lessons for the actual experiment and its limits.
