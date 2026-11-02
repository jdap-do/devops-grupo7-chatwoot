"""Contract validation against a controlled upstream; never modifies Chatwoot."""
import asyncio
import sys

sys.path.insert(0, "/app")
from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.test_utils import TestServer
import gateway


async def main():
    async def respond(request):
        if request.path == "/slow":
            await asyncio.sleep(1.1)
        if request.path == "/timeout":
            await asyncio.sleep(5.2)
        if request.path == "/echo":
            return web.Response(body=await request.read(), headers={"Set-Cookie": "lab=value"})
        status = {"/missing": 404, "/failure": 503}.get(request.path, 200)
        return web.Response(status=status, text="controlled")

    upstream = web.Application()
    upstream.router.add_route("*", "/{path:.*}", respond)
    async with TestServer(upstream) as source:
        async with ClientSession(timeout=ClientTimeout(total=5, ceil_threshold=float("inf")), auto_decompress=False) as upstream_client:
            app = web.Application()
            app["client"] = upstream_client
            app["upstream"] = str(source.make_url("/")).rstrip("/")
            app.router.add_route("*", "/{path:.*}", gateway.proxy)
            async with TestServer(app) as target, ClientSession() as client:
                async def request(path, expected, method="GET", **kwargs):
                    async with client.request(method, target.make_url(path), **kwargs) as response:
                        await response.read()
                        assert response.status == expected, (path, response.status)
                        return response

                labels = {"project": gateway.project, "environment": gateway.environment, "method": "GET"}
                def count(status):
                    return gateway.registry.get_sample_value("unal_chatwoot_http_requests_total",
                                                             {**labels, "status_class": status})
                await request("/", 200)
                await request("/missing", 404)
                await request("/failure", 503)
                await request("/slow", 200)
                await request("/timeout", 504)
                before = count("2xx")
                for path in gateway.EXCLUDED:
                    await request(path, 200)
                assert count("2xx") == before, "Excluded paths changed eligible population"
                response = await request("/echo", 200, method="POST", data=b"lab-payload")
                assert response.headers["Set-Cookie"] == "lab=value"
                await request("/", 501, headers={"Upgrade": "websocket"})
                app["upstream"] = "http://127.0.0.1:1"
                await request("/", 502)
                assert count("2xx") == 2
                assert count("4xx") == 1
                assert count("5xx") == 3
                for status in gateway.CLASSES:
                    histogram_count = gateway.registry.get_sample_value(
                        "unal_chatwoot_http_request_duration_seconds_count", {**labels, "status_class": status})
                    assert histogram_count == count(status), (status, histogram_count, count(status))
                samples = gateway.registry.get_sample_value(
                    "unal_chatwoot_http_request_duration_seconds_bucket",
                    {**labels, "status_class": "2xx", "le": "1.0"})
                assert samples == 1, "Slow request must be outside the one-second bucket"
                assert gateway.registry.get_sample_value("unal_chatwoot_http_in_flight_requests",
                    {"project": gateway.project, "environment": gateway.environment}) == 0
                print("PASS: 200, 404, 503, 504 timeout, 502 connection, POST/cookie, exclusions, WebSocket exclusion")
                print("PASS: histogram/count parity, one-second bucket, zero initialization and in-flight recovery")
                print("NOTE: controlled upstream; no production incident was executed")


asyncio.run(main())
