"""Proxy de lecturas para GameDay; usa aiohttp de la imagen existente del gateway."""
import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import re
import time

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from gateway import READ_ROUTE, headers_without_hops

SETTINGS = Path('/gameday/config.json')
SETTINGS_POLL_SECONDS = 0.1
UPSTREAM_TIMEOUT_SECONDS = 5


async def lifecycle(app):
    control = {'delay_ms': json.loads(SETTINGS.read_text())['delay_ms'], 'recovered': asyncio.Event()}
    app['control'] = control

    async def watch_settings():
        while True:
            control['delay_ms'] = json.loads(SETTINGS.read_text())['delay_ms']
            if control['delay_ms'] == 0:
                control['recovered'].set()
            await asyncio.sleep(SETTINGS_POLL_SECONDS)

    watcher = asyncio.create_task(watch_settings())
    async with ClientSession(timeout=ClientTimeout(total=UPSTREAM_TIMEOUT_SECONDS), auto_decompress=False) as session:
        app['client'] = session
        try:
            yield
        finally:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher


async def health(request):
    return web.json_response({'delay_ms': request.app['control']['delay_ms']})


async def proxy(request):
    if request.method != 'GET' or not READ_ROUTE.fullmatch(request.path):
        return web.Response(status=404)
    started = time.monotonic()
    delay_ms = request.app['control']['delay_ms']
    status = 502
    try:
        if delay_ms:
            try:
                # recover despierta tambien solicitudes que ya estaban esperando.
                await asyncio.wait_for(request.app['control']['recovered'].wait(), timeout=delay_ms / 1000)
            except asyncio.TimeoutError:
                pass
        async with request.app['client'].get(
            request.app['upstream'] + request.raw_path,
            headers=headers_without_hops(request.headers), allow_redirects=False,
        ) as response:
            body = await response.read()
            status = response.status
            return web.Response(status=status, body=body, headers=headers_without_hops(response.headers))
    except asyncio.TimeoutError:
        status = 504
        return web.Response(status=status, text='Upstream timeout')
    except ClientError:
        return web.Response(status=status, text='Upstream unavailable')
    finally:
        print(json.dumps({'event': 'latency_request', 'at_unix': time.time(),
                          'operation': re.sub(r'/[0-9]+', '/:id', request.path),
                          'configured_delay_ms': delay_ms, 'status': status,
                          'duration_seconds': round(time.monotonic() - started, 3)}), flush=True)


def create_app(upstream):
    app = web.Application()
    app['upstream'] = upstream.rstrip('/')
    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/health', health)
    app.router.add_route('*', '/{path:.*}', proxy)
    return app


if __name__ == '__main__':
    web.run_app(create_app(os.environ['UPSTREAM_URL']), host='0.0.0.0', port=8080, access_log=None)
