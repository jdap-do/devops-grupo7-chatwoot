"""Run on the GCP VM. The DuckDNS token is never printed or passed to a process."""
import ipaddress
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    token = Path('/srv/chatwoot/config/duckdns-token').read_text().strip()
    if not token:
        raise ValueError('Missing token')
    request = Request(
        'http://metadata.google.internal/computeMetadata/v1/instance/'
        'network-interfaces/0/access-configs/0/external-ip',
        headers={'Metadata-Flavor': 'Google'},
    )
    with urlopen(request, timeout=10) as response:
        address = str(ipaddress.IPv4Address(response.read().decode().strip()))
    parameters = urlencode({
        'domains': 'grupo7-chatwoot-unal,grupo7-grafana-unal',
        'token': token,
        'ip': address,
    })
    with urlopen('https://www.duckdns.org/update?' + parameters, timeout=30) as response:
        if response.read().decode().strip() != 'OK':
            raise ValueError('DuckDNS rejected update')
    print('DuckDNS: both names updated to the VM external IP.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # HTTP exceptions may contain the request URL, including the token.
        print('DuckDNS update failed; check private token, network and VM metadata.', file=sys.stderr)
        sys.exit(1)
