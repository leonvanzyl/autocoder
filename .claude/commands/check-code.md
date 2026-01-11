---
description:
---

Run the following commands and ensure the code is clean.

From project root:

# Python linting

ruff check .

# Security tests

python test_security.py

From ui/ directory:
cd ui

# ESLint (will fail until we add the config)

npm run lint

# TypeScript check + build

npm run build

One-liner to run everything:
ruff check . && python test_security.py && cd ui && npm run lint && npm run build

Or if you want to see all failures at once (doesn't stop on first error):
ruff check .; python test_security.py; cd ui && npm run lint; npm run build
