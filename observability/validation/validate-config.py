"""Validate configuration syntax and prepare dashboard queries for promtool, offline.

Requires PyYAML 6.0.3. Does not start services or contact Chatwoot.
"""

import argparse
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY = ROOT / 'observability'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dashboard-rules', type=Path, required=True)
    args = parser.parse_args()

    yaml_count = 0
    for directory, subdirectories, filenames in os.walk(OBSERVABILITY):
        subdirectories[:] = [name for name in subdirectories if name not in ('node_modules', '__pycache__')]
        for filename in filenames:
            if Path(filename).suffix in ('.yml', '.yaml'):
                path = Path(directory) / filename
                list(yaml.safe_load_all(path.read_text(encoding='utf-8')))
                yaml_count += 1

    dashboard = json.loads((OBSERVABILITY / 'grafana/dashboards/chatwoot-sre.json').read_text(encoding='utf-8'))
    if dashboard['uid'] != 'chatwoot-sre-unal':
        raise ValueError('El UID del dashboard no coincide con el contrato.')
    panels = dashboard['panels']
    if len({panel['id'] for panel in panels}) != len(panels):
        raise ValueError('El dashboard contiene identificadores de panel repetidos.')
    if [variable['name'] for variable in dashboard['templating']['list']] != ['project', 'environment']:
        raise ValueError('Las variables del dashboard no coinciden con el contrato.')

    rules = []
    for panel in panels:
        for target in panel.get('targets', []):
            expression = target['expr']
            if target['datasource']['uid'] != 'prometheus-unal':
                raise ValueError(f"Datasource incompatible en el panel {panel['id']}.")
            if '$project' not in expression or '$environment' not in expression:
                raise ValueError(f"Falta el filtro de proyecto o entorno en el panel {panel['id']}.")
            expression = expression.replace('$project', 'devops-grupo7').replace('$environment', 'lab')
            rules.append({'record': f'ci_dashboard_query_{len(rules) + 1}', 'expr': expression})
    if not rules:
        raise ValueError('El dashboard no contiene consultas para validar.')

    args.dashboard_rules.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_rules.write_text(yaml.safe_dump({'groups': [{'name': 'dashboard-syntax', 'rules': rules}]}), encoding='utf-8')
    print(f'YAML validado: {yaml_count} archivos. Dashboard: {len(panels)} paneles y {len(rules)} consultas para promtool.')


if __name__ == '__main__':
    main()
