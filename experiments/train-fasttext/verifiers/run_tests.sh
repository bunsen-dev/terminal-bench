#!/bin/bash
set -euo pipefail

/opt/train-fasttext-verifier/bin/pytest /bunsen/verifiers/test_outputs.py -v
