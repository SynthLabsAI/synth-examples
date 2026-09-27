# Review-permissions teaching example

Follow https://synthlabs.mintlify.app/tutorials/first-review . This directory contains a complete
Harbor task package, reviewer profile and example evaluation/training plans.
Upload only review-permissions/, not this enclosing directory.

The task deliberately contains one small authorization regression. Its verifier
checks an executable counterexample, not all aspects of natural-language review
quality. A good score on this example does not establish general reviewer quality.
The verifier is not copied into the actor image.

The profile permits Read, Glob, Grep, Bash and Write without interactive approval.
It is intended for the prepared managed task, not arbitrary host execution.
Do not run it locally without reviewing its permissions and files.

Sign in with `synth login`, then run the read-only setup check:
`python3 check_setup.py`. The evaluation plan requests exactly one trial.
The Docker base is pinned by image digest.

The included training plan is an illustration for a multi-task practice dataset.
It requests 24 slots. It is not a recommendation to train only on this one toy
task or evidence that doing so will improve a real code reviewer.
