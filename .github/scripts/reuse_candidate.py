"""Promover una imagen reciente de CI confiable solo para un arbol Git identico."""
from datetime import datetime, timezone, timedelta
import json
import os
import re
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def api(path):
    request = Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + '/' + path,
                      headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                               'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def trusted_run(run, source, repository_id):
    return (run.get('head_sha') == source
            and run.get('event') == 'push'
            and run.get('head_branch') in ('develop', 'main')
            and run.get('conclusion') == 'success'
            and str((run.get('head_repository') or {}).get('id')) == str(repository_id))


def validate_candidate(image, expected_tree, commit_tree, runs, repository_id, now):
    labels = image.get('Config', {}).get('Labels') or {}
    source = labels.get('org.opencontainers.image.revision', '')
    if not re.fullmatch('[0-9a-f]{40}', source):
        return None
    if labels.get('io.grupo7.source-tree') != expected_tree or commit_tree != expected_tree:
        return None
    created = datetime.fromisoformat(image['Created'].replace('Z', '+00:00'))
    if created > now + timedelta(minutes=5) or now - created > timedelta(hours=24):
        return None
    if not any(trusted_run(run, source, repository_id) for run in runs):
        return None
    return source


def output(**values):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        for key, value in values.items():
            stream.write(f'{key}={value}\n')


def main():
    repository = os.environ['IMAGE']
    tree = os.environ['SOURCE_TREE']
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or not re.fullmatch('[0-9a-f]{40}', tree):
        raise SystemExit('Promocion permitida solo en main y con arbol Git valido')
    tag = f'{repository}:tree-{tree}'
    pulled = subprocess.run(['docker', 'pull', tag], capture_output=True, text=True)
    if pulled.returncode:
        if re.search(r'manifest unknown|manifest .*not found|not found', pulled.stderr, re.I):
            print('Sin candidata publicada: construir y validar normalmente.')
            output(reused='false')
            return
        raise SystemExit('No se pudo consultar GHCR; no promover una imagen sin verificar.')
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', tag], text=True))[0]
    labels = image.get('Config', {}).get('Labels') or {}
    source = labels.get('org.opencontainers.image.revision', '')
    if not re.fullmatch('[0-9a-f]{40}', source):
        print('Candidata sin revision valida; reconstruir.')
        output(reused='false')
        return
    commit = api('git/commits/' + source)
    query = urlencode({'head_sha': source, 'event': 'push', 'status': 'success', 'per_page': 30})
    runs = api('actions/workflows/grupo7-ci.yml/runs?' + query)['workflow_runs']
    accepted = validate_candidate(image, tree, commit['tree']['sha'], runs,
                                  os.environ['GITHUB_REPOSITORY_ID'], datetime.now(timezone.utc))
    digests = [digest for digest in image.get('RepoDigests', [])
               if re.fullmatch(re.escape(repository) + r'@sha256:[0-9a-f]{64}', digest)]
    if accepted is None or len(digests) != 1:
        print('Candidata no aprobada, vencida o distinta al contenido de main; reconstruir.')
        output(reused='false')
        return
    output(reused='true', image=digests[0], source_revision=accepted)
    print(f'Promocion de contenido identico: fuente {accepted}, arbol {tree}, digest {digests[0]}')


if __name__ == '__main__':
    main()
