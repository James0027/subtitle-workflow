"""Re-run local acceptance checks with ordinary Windows test-directory permissions."""
import os
import sys
from pathlib import Path
import pytest

repo = Path(__file__).resolve().parents[4]
os.chdir(repo)
sys.path.insert(0, str(repo))
original_mkdir = os.mkdir

def test_mkdir(path, mode=0o777, *, dir_fd=None):
    return original_mkdir(path, 0o777, dir_fd=dir_fd)

os.mkdir = test_mkdir
suite = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
files = {
    'baseline': ['tests/unit/test_storage_media.py', 'tests/integration/test_asr_provider_failure.py', 'code/backend/modules/asr_alignment/tests/test_asr_alignment.py'],
    'intake': ['tests/integration/test_intake_api.py', 'tests/integration/test_asr_api.py'],
}[suite]
args = files + ['-q', '-p', 'no:cacheprovider', '--basetemp', f'data/resume-repeat-{suite}-{os.getpid()}', '--junitxml', f'docs/08-test-reports/20261022/resume/repeat-{suite}.xml']
raise SystemExit(pytest.main(args))
