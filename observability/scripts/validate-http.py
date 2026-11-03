"""Gateway v3 checks against a controlled upstream, without touching Chatwoot."""
import asyncio
import sys
sys.path.insert(0, '/app')
from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.test_utils import TestServer
import gateway


async def main():
    async def respond(request):
        await asyncio.sleep(float(request.query.get('delay', '0')))
        return web.json_response({'test': True}, status=int(request.query.get('status', '200')))

    for status, cause, expected in [(200,'success','good'), (302,'redirect','excluded'),
                                   (400,'unknown','bad'), (401,'service_failure','bad'),
                                   (429,'service_overload','bad'), (429,'unknown','bad'),
                                   (400,'client_confirmed','excluded'), (401,'client_confirmed','excluded'),
                                   (404,'client_confirmed','excluded'), (429,'client_confirmed','excluded'),
                                   (500,'service_failure','bad'), (503,'service_failure','bad'),
                                   (504,'service_failure','bad')]:
        assert gateway.classify(status, cause) == expected
    upstream = web.Application()
    upstream.router.add_route('*', '/{path:.*}', respond)
    async with TestServer(upstream) as source, ClientSession(
            timeout=ClientTimeout(total=5, ceil_threshold=float('inf')), auto_decompress=False) as session:
        app = web.Application()
        app['client'] = session
        app['upstream'] = str(source.make_url('/')).rstrip('/')
        app.router.add_route('*', '/{path:.*}', gateway.proxy)
        async with TestServer(app) as target, ClientSession() as client:
            async def request(path, status, method='GET', headers=None):
                async with client.request(method, target.make_url(path), headers=headers,
                                          allow_redirects=False) as response:
                    await response.read()
                    assert response.status == status, (path, response.status)
            route = '/api/v1/accounts/1/conversations'
            for suffix in ('/conversations', '/conversations/search', '/conversations/1/messages', '/contacts'):
                await request('/api/v1/accounts/1' + suffix, 200)
            await request(route + '?delay=0.6', 200)
            await request(route + '?status=302', 302)
            await request(route + '?status=401', 401,
                          headers={'X-Availability-Result': 'excluded'})
            await request(route + '?status=429', 429)
            await request(route + '?status=503', 503)
            await request(route + '?delay=5.2', 504)
            for path in ('/', '/assets/example.js', '/healthz', '/api/v1/accounts/1/labels'):
                await request(path, 200)
            await request(route, 200, method='POST')
            await request(route, 501, headers={'Upgrade': 'websocket'})
            app['upstream'] = 'http://127.0.0.1:1'
            await request(route, 502)
            common = {'project': gateway.project, 'environment': gateway.environment, 'method': 'GET'}
            for status, result, expected in [('2xx','good',5), ('3xx','excluded',1),
                                              ('4xx','bad',2), ('5xx','bad',3)]:
                labels = {**common, 'status_class': status, 'availability_result': result}
                assert gateway.registry.get_sample_value('unal_chatwoot_http_requests_total', labels) == expected
                assert gateway.registry.get_sample_value('unal_chatwoot_http_request_duration_seconds_count', labels) == expected
            labels = {**common, 'status_class': '2xx', 'availability_result': 'good', 'le': '0.5'}
            assert gateway.registry.get_sample_value('unal_chatwoot_http_request_duration_seconds_bucket', labels) == 4
            assert gateway.active._value.get() == 0
    print('PASS: four GET routes, excluded static/health/POST/WebSocket, query strings')
    print('PASS: good/bad/excluded classification, conservative 4xx, spoofed header ignored')
    print('PASS: 500 ms bucket, 502 connection, 504 deadline, histogram/count parity')


asyncio.run(main())
