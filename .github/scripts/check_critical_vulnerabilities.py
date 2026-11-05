"""Bloquea criticas corregibles; excepcion temporal tras probar ImageMagick en CI."""
import datetime
import json
import sys

EXPIRES = datetime.date(2026, 11, 12)
ADVISORY = 'GHSA-f3w6-w445-fwh9'


def is_mitigated(vulnerability, today):
    return (
        today < EXPIRES
        and vulnerability.get('VulnerabilityID') == ADVISORY
        and vulnerability.get('PkgName') == 'activestorage'
        and vulnerability.get('InstalledVersion') == '7.2.3.1'
    )


def main():
    report = json.load(open(sys.argv[1], encoding='utf-8'))
    if not isinstance(report.get('Results'), list) or not report['Results']:
        raise SystemExit('FAIL: reporte Trivy vacio o no reconocido')
    blocked = []
    today = datetime.datetime.now(datetime.timezone.utc).date()
    for result in report['Results']:
        for item in result.get('Vulnerabilities') or []:
            if item.get('Severity') != 'CRITICAL' or not item.get('FixedVersion'):
                continue
            if is_mitigated(item, today):
                print(f'MITIGACION TEMPORAL: {ADVISORY}; vence {EXPIRES}; ver docs/entrega4/SEGURIDAD_IMAGEN.md')
            else:
                blocked.append(item)
                print(f"FAIL: {item.get('PkgName')} {item.get('InstalledVersion')}: {item.get('VulnerabilityID')}")
    if today >= EXPIRES:
        raise SystemExit('FAIL: revisar y retirar la excepcion temporal vencida')
    if blocked:
        raise SystemExit(1)
    print('PASS: ninguna vulnerabilidad critica corregible sin mitigacion autorizada')


if __name__ == '__main__':
    main()
