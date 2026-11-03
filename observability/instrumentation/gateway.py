"""Laboratory HTTP gateway. WebSocket traffic is outside the SLI contract."""
import asyncio
import os
import re
import time

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from multidict import CIMultiDict
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "OTHER")
CLASSES = ("2xx", "3xx", "4xx", "5xx")
EXCLUDED = {"/metrics", "/health", "/healthz", "/readyz"}
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade"}
BUCKETS = (.05, .1, .25, .5, 1, 2.5, 5, 10, float("inf"))
LABELS = ("project", "environment", "method", "status_class", "availability_result")
RESULTS = ("good", "bad", "excluded")
READ_ROUTE = re.compile(r"^/api/v1/accounts/[0-9]+/(?:conversations(?:/search|/[0-9]+/messages)?|contacts)$")
registry = CollectorRegistry()
requests = Counter("unal_chatwoot_http_requests_total", "Completed eligible HTTP requests",
                   LABELS, registry=registry)
duration = Histogram("unal_chatwoot_http_request_duration_seconds", "HTTP gateway duration",
                     LABELS, buckets=BUCKETS, registry=registry)
in_flight = Gauge("unal_chatwoot_http_in_flight_requests", "Eligible requests in progress",
                  ("project", "environment"), registry=registry)
project = os.getenv("PROJECT", "devops-grupo7")
environment = os.getenv("ENVIRONMENT", "lab")
for method in METHODS:
    for status_class in CLASSES:
        for result in RESULTS:
            requests.labels(project, environment, method, status_class, result)
            duration.labels(project, environment, method, status_class, result)
active = in_flight.labels(project, environment)


def classify(status, attribution="unknown"):
    if 200 <= status < 300:
        return "good"
    if 300 <= status < 400 or (400 <= status < 500 and attribution == "client_confirmed"):
        return "excluded"
    return "bad"


def headers_without_hops(headers):
    connection_tokens = {token.strip().lower() for token in headers.get("Connection", "").split(",")}
    return CIMultiDict((key, value) for key, value in headers.items()
                       if key.lower() not in HOP_HEADERS | connection_tokens)


async def proxy(request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return web.Response(status=501, text="WebSocket is outside this laboratory gateway contract")
    eligible = request.method == "GET" and READ_ROUTE.fullmatch(request.path) is not None
    method = request.method if request.method in METHODS else "OTHER"
    started = time.monotonic()
    status = 502
    if eligible:
        active.inc()
    try:
        headers = headers_without_hops(request.headers)
        headers["X-Forwarded-Proto"] = request.scheme
        headers["X-Forwarded-Host"] = request.host
        # The gateway is the first trusted hop; ignore user-supplied forwarding addresses.
        headers["X-Forwarded-For"] = request.remote or "unknown"
        async with request.app["client"].request(
            request.method, request.app["upstream"] + request.raw_path,
            headers=headers, data=request.content, allow_redirects=False,
        ) as upstream:
            body = await upstream.read()
            status = upstream.status
            return web.Response(status=status, body=body, headers=headers_without_hops(upstream.headers))
    except asyncio.TimeoutError:
        status = 504
        return web.Response(status=status, text="Upstream timeout")
    except ClientError:
        return web.Response(status=status, text="Upstream unavailable")
    finally:
        if eligible:
            status_class = f"{status // 100}xx" if 200 <= status < 600 else "5xx"
            # No client-provided header may assert attribution. Without independently
            # verified client responsibility, every 4xx is conservatively bad.
            result = classify(status)
            requests.labels(project, environment, method, status_class, result).inc()
            duration.labels(project, environment, method, status_class, result).observe(time.monotonic() - started)
            active.dec()


async def metrics(_request):
    return web.Response(body=generate_latest(registry),
                        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


async def run():
    upstream = os.environ["UPSTREAM_URL"].rstrip("/")
    async with ClientSession(timeout=ClientTimeout(total=5, ceil_threshold=float("inf")), auto_decompress=False) as client:
        app = web.Application(client_max_size=40 * 1024 * 1024)
        app["client"] = client
        app["upstream"] = upstream
        app.router.add_route("*", "/{path:.*}", proxy)
        metrics_app = web.Application()
        metrics_app.router.add_get("/metrics", metrics)
        metrics_app.router.add_get("/healthz", lambda _: web.Response(text="ok"))
        runners = [web.AppRunner(app, access_log=None), web.AppRunner(metrics_app, access_log=None)]
        try:
            for runner, port in zip(runners, (8080, 9100)):
                await runner.setup()
                await web.TCPSite(runner, "0.0.0.0", port).start()
            await asyncio.Event().wait()
        finally:
            for runner in runners:
                await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
