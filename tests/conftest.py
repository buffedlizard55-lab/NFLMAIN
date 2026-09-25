"""Make the pipeline importable as flat modules (it is a script collection, not a package)."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(REPO_ROOT, "pipeline")
if PIPELINE not in sys.path:
    sys.path.insert(0, PIPELINE)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir():
    return os.path.join(REPO_ROOT, "tests", "fixtures")
