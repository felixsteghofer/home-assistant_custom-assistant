"""Validate the single-integration HACS layout and public release metadata."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
components = [p for p in (ROOT / 'custom_components').iterdir() if p.is_dir() and p.name != '__pycache__']
assert len(components) == 1, 'HACS requires one integration per repository'
component = components[0]
manifest = json.loads((component / 'manifest.json').read_text())
for key in ('domain', 'documentation', 'issue_tracker', 'codeowners', 'name', 'version'):
    assert manifest.get(key), f'Missing manifest metadata: {key}'
assert manifest['domain'] == component.name == 'bunker_codex'
assert manifest['config_flow'] is True
assert manifest['codeowners'] == ['@felixsteghofer']
for key in ('documentation', 'issue_tracker'):
    assert manifest[key].startswith('https://github.com/felixsteghofer/home-assistant_custom-assistant')
hacs = json.loads((ROOT / 'hacs.json').read_text())
assert hacs['name'] == manifest['name']
assert hacs['homeassistant'] == '2026.10.1'
assert hacs['render_readme'] is True
for name in ('__init__.py', 'config_flow.py', 'conversation.py', 'client.py', 'const.py'):
    assert (component / name).is_file(), f'Missing runtime file: {name}'
strings = json.loads((component / 'strings.json').read_text())
for path in (component / 'translations').glob('*.json'):
    translated = json.loads(path.read_text())
    for section in ('config', 'options'):
        assert set(translated[section]['step']) == set(strings[section]['step'])
print('HACS package structure, metadata and translations: PASS')
