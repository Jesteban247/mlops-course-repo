#!/usr/bin/env python3
"""Configure the Argo CD admin password using the private project .env."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess

path = Path(__file__).resolve().parent.parent / '.env'
if not path.is_file():
    raise SystemExit('Missing project_3/.env')
lines = path.read_text().splitlines()
values = {}
for line in lines:
    if '=' not in line or line.lstrip().startswith('#'):
        continue
    key, value = line.split('=', 1)
    if key in ('ARGOCD_USERNAME', 'ARGOCD_PASSWORD'):
        parts = shlex.split(value, comments=True)
        values[key] = parts[0] if len(parts) == 1 else ''
username = values.get('ARGOCD_USERNAME', 'admin')
if username != 'admin':
    raise SystemExit('ARGOCD_USERNAME must be admin')
password = values.get('ARGOCD_PASSWORD')
if not password or password == 'replace-me':
    password = secrets.token_urlsafe(24)
if 'ARGOCD_USERNAME' not in values or values.get('ARGOCD_PASSWORD') != password:
    lines = [line for line in lines if not line.startswith(('ARGOCD_USERNAME=', 'ARGOCD_PASSWORD='))]
    lines.extend(['ARGOCD_USERNAME=admin', 'ARGOCD_PASSWORD=' + password])
    path.write_text('\n'.join(lines) + '\n')
    os.chmod(path, 0o600)
if len(password.encode()) > 72 or any(c in password for c in '\r\n\x00'):
    raise SystemExit('ARGOCD_PASSWORD must be at most 72 bytes and fit on one line')
result = subprocess.run(
    ['kubectl', '-n', 'argocd', 'exec', '-i', 'deploy/argocd-server', '--', 'argocd', 'account', 'bcrypt'],
    input=password + '\n', text=True, stdout=subprocess.PIPE, check=True)
match = re.search(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}', result.stdout)
if not match:
    raise SystemExit('Argo CD did not return a valid bcrypt hash')
patch = {'stringData': {'admin.password': match.group(0),
                        'admin.passwordMtime': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')}}
subprocess.run(['kubectl', '-n', 'argocd', 'patch', 'secret', 'argocd-secret', '--type=merge', '--patch-file=/dev/stdin'],
               input=json.dumps(patch), text=True, check=True)
print('Argo CD admin login configured from project_3/.env')
