#!/bin/sh
set -eu
python3 /tests/grade.py --review /logs/artifacts/review.json --reward /logs/verifier/reward.json
