"""Prueba la politica efectiva en la imagen final, antes de permitir la excepcion."""
import subprocess
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path

policy = subprocess.check_output([
    'docker', 'run', '--rm', '--network=none', '--entrypoint', 'cat',
    sys.argv[1], '/etc/ImageMagick-6/policy.xml',
])
# Debian incluye un comentario de ejemplo anidado que su lector tolera.
# Retirar comentarios antes del analisis XML estricto; probar el lector real abajo.
effective = ET.fromstring(re.sub(rb'<!--.*?-->', b'', policy, flags=re.S))
expected = ET.fromstring('<policymap>' + Path('docker/security/imagemagick-policy.xml').read_text() + '</policymap>')
for rule in expected:
    if not any(rule.attrib == actual.attrib for actual in effective):
        raise SystemExit(f'FAIL: falta regla {rule.attrib}')

script = r'''
set -eu
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
convert -size 1x1 xc:white "$work/allowed.png"
identify "$work/allowed.png"
convert "$work/allowed.png" "$work/allowed.jpg"
identify "$work/allowed.jpg"
# Probar lectores presentes en Debian; otros alias pueden no estar compilados.
for coder in MSL TEXT PDF PS MPC; do
  if identify "$coder:$work/allowed.png" >"$work/result" 2>&1; then
    echo "FAIL: $coder permitido"; exit 1
  fi
  # Un error de formato no demuestra que la politica haya bloqueado el lector.
  grep -qi 'security policy' "$work/result" || { cat "$work/result"; exit 1; }
done
printf 'solo un marcador de prueba' > "$work/marker"
if convert -background white "label:@$work/marker" "$work/indirect.png" >"$work/result" 2>&1; then
  echo 'FAIL: lectura indirecta permitida'; exit 1
fi
grep -qi 'security policy' "$work/result"
echo 'PASS: PNG/JPEG funcionan; coders peligrosos y lectura indirecta bloqueados'
'''
subprocess.run(
    ['docker', 'run', '--rm', '-i', '--network=none', '--entrypoint', 'sh', sys.argv[1], '-s'],
    input=script.encode('utf-8'), check=True,
)
