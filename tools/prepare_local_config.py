"""Create new-machine configuration. Refuses to replace existing config or keys."""
import argparse
import json
import os
from pathlib import Path
import secrets


def prepare(root):
    root = Path(root).expanduser().resolve()
    if not (root/'gateway/auth.py').is_file() or not (root/'mcp-lab/aitob_assistant_service.py').is_file():
        raise ValueError('Selected folder is not the AItoB project root')
    targets = [root/'gateway/credentials/keys.json', root/'gateway/credentials/hr.key',
               root/'gateway/credentials/finance.key', root/'open-webui/.env',
               root/'services/.env', root/'services/compose.json']
    if any(path.exists() or path.is_symlink() for path in targets):
        raise FileExistsError('Existing configuration found; no keys or config replaced')
    if any(c in str(root) for c in ['\n', '\r', "'", '$']):
        raise ValueError('Use a project path without newline, quote or dollar sign')
    os.umask(0o077)
    for folder in ['gateway/credentials', 'gateway/data/finance', 'gateway/runtime/finance',
                   'gmail-lab/credentials', 'logs', 'services', 'open-webui']:
        (root/folder).mkdir(parents=True, exist_ok=True)
    hr, finance = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    mapping = {hr: {'user': 'may', 'team': 'HR', 'role': 'hr_reader'},
               finance: {'user': 'ton', 'team': 'Finance', 'role': 'finance_reader'}}
    content = [json.dumps(mapping, indent=2), hr+'\n', finance+'\n',
               'WEBUI_SECRET_KEY='+secrets.token_urlsafe(48)+'\n',
               "AITOB_LAB_ROOT='"+str(root)+"'\n",
               (root/'services/compose.template.json').read_text()]
    for path, text in zip(targets, content):
        with path.open('x', encoding='utf-8') as handle:
            handle.write(text)
        path.chmod(0o600)
    return targets


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab', required=True)
    args = parser.parse_args()
    for path in prepare(args.lab):
        print('Created local configuration:', path)
    print('No service started. No keys displayed. Configure Gmail ownership separately.')
