"""Keep an optional legacy profile installer from stopping other businesses.

Run before uvicorn. No credentials or installer output are written to logs.
Profiles are checked on requests; service liveness is not profile readiness.
"""
import os
from pathlib import Path
import subprocess
import sys


def bootstrap_legacy_profile():
    installer = Path('/etc/secrets/install_flora_profile.py')
    if not os.environ.get('BB_FLORA_PROFILE'):
        print('BB startup: legacy profile not configured; shared engine can start.')
        return
    if not installer.is_file():
        print('BB startup: no legacy installer; configured profiles checked on request.')
        return
    try:
        result = subprocess.run([sys.executable, str(installer)], capture_output=True,
                                timeout=60, check=False)
        if result.returncode:
            print('BB startup: legacy profile installer failed; profile readiness must be checked.')
        else:
            print('BB startup: legacy profile installer completed.')
    except (OSError, subprocess.TimeoutExpired):
        print('BB startup: legacy profile installer unavailable; other profiles remain independent.')


if __name__ == '__main__':
    bootstrap_legacy_profile()
