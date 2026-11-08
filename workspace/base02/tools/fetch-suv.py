#!/usr/bin/env python3
"""Fetch only the external SUV asset used by the unchanged Econ world."""
import json
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parent.parent
commit = '8163eb4b5e7e21985c6591d1c0bfb56468c0093f'
tree = json.loads((project / 'evidence/initial/gazebo-models-tree.json').read_text())
records = []
for item in tree['tree']:
    if item['type'] != 'blob' or not (item['path'].startswith('suv/') or item['path'] == 'LICENSE'):
        continue
    destination = project / 'assets/gazebo_models' / item['path']
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://raw.githubusercontent.com/osrf/gazebo_models/{commit}/{item["path"]}'
    subprocess.run(['curl', '-fL', '--connect-timeout', '10', '--max-time', '120', url, '-o', str(destination)], check=True)
    records.append(dict(path=item['path'], git_blob=item['sha'], url=url))
(project / 'evidence/initial/suv-provenance.json').write_text(json.dumps(dict(repository='https://github.com/osrf/gazebo_models', commit=commit, files=records), indent=2))
