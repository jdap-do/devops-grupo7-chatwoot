import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const validationDir = dirname(fileURLToPath(import.meta.url));
const dashboardSource = await readFile(resolve(validationDir, '../grafana/dashboards/chatwoot-sre.json'), 'utf8');
const dashboard = JSON.parse(dashboardSource);
const outputDir = resolve(validationDir, '../evidence/david/dashboard');
const grafanaUrl = process.env.VALIDATION_GRAFANA_URL || 'http://127.0.0.1:13005';
const prometheusUrl = process.env.VALIDATION_PROMETHEUS_URL || 'http://127.0.0.1:19090';
const fixtureUrl = process.env.VALIDATION_METRICS_URL || 'http://127.0.0.1:18091';
for (const url of [grafanaUrl, prometheusUrl, fixtureUrl]) {
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(url).hostname), 'Solo se valida el entorno sintético local');
}
const uid = 'chatwoot-sre-unal';
assert.equal(dashboard.uid, uid);
assert.equal(new Set(dashboard.panels.map(panel => panel.id)).size, dashboard.panels.length);
assert.deepEqual(dashboard.templating.list.map(variable => variable.name), ['project', 'environment']);
const queries = dashboard.panels.flatMap(panel => (panel.targets || []).map(query => ({ panel, query })));
for (const { panel, query } of queries) {
  assert.equal(query.datasource.uid, 'prometheus-unal', panel.title);
  assert(query.expr.includes('$project') && query.expr.includes('$environment'), panel.title);
  assert(!query.expr.includes('or vector(0)'), 'No se convierte falta de datos en cero');
}
const summary = { synthetic: true, dashboardUid: uid, dashboardSha256: createHash('sha256').update(dashboardSource).digest('hex'), panels: dashboard.panels.length, queries: queries.length, checks: [] };
await mkdir(outputDir, { recursive: true });

async function json(url, options) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(15000) });
  assert(response.ok, `${new URL(url).pathname}: HTTP ${response.status}`);
  return response.status === 204 ? null : response.json();
}

async function waitFor(label, check, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const result = await check();
      if (result) return result;
    } catch (error) {
      lastError = error;
    }
    await new Promise(resolveWait => setTimeout(resolveWait, 2000));
  }
  throw new Error(`${label}: ${lastError?.message || 'no se alcanzó el estado esperado'}`);
}

const interpolate = expression => expression.replaceAll('$project', 'devops-grupo7').replaceAll('$environment', 'lab');
async function prom(expression) {
  const response = await json(`${prometheusUrl}/api/v1/query?query=${encodeURIComponent(expression)}`);
  assert.equal(response.status, 'success');
  return response.data.result;
}
const selector = (name, extra = '') => `${name}{project="devops-grupo7",environment="lab"${extra ? `,${extra}` : ''}}`;
async function number(expression) {
  const result = await prom(expression);
  return result.length ? Number(result[0].value[1]) : null;
}
async function scenario(name) {
  const state = await json(`${fixtureUrl}/scenario`);
  assert.equal(state.synthetic, true, 'El control debe pertenecer al generador sintético');
  await json(`${fixtureUrl}/scenario`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario: name }) });
}
async function grafanaQuery(expression) {
  const now = Date.now();
  const response = await json(`${grafanaUrl}/api/ds/query`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: String(now - 900000), to: String(now), queries: [{ refId: 'A', expr: expression,
      datasource: { type: 'prometheus', uid: 'prometheus-unal' }, instant: true, range: false,
      format: 'time_series', intervalMs: 15000, maxDataPoints: 1000 }] }),
  });
  assert(!response.results.A.error, response.results.A.error);
  return response.results.A.frames || [];
}

await waitFor('Arranque de Grafana', async () => (await json(`${grafanaUrl}/api/health`)).database === 'ok');
await scenario('healthy');
await waitFor('Muestras iniciales', async () => await number(selector('unal_chatwoot:slo_sli:ratio', 'slo="availability",window="30d"')) !== null);
const imported = await json(`${grafanaUrl}/api/dashboards/uid/${uid}`);
assert.equal(imported.dashboard.panels.length, dashboard.panels.length);
assert.deepEqual(imported.dashboard.panels.map(panel => panel.title), dashboard.panels.map(panel => panel.title), 'Grafana debe cargar la versión actual del JSON');
assert.deepEqual(imported.dashboard.panels.flatMap(panel => (panel.targets || []).map(query => query.expr)), queries.map(({ query }) => query.expr));
for (const panel of dashboard.panels.filter(item => (item.targets || []).some(query => query.expr.includes('slo_budget_remaining')))) {
  assert.notEqual(panel.fieldConfig.defaults.min, 0, 'El presupuesto negativo no se recorta');
}
assert(imported.meta.folderTitle.includes('SINTÉTICA'), 'La carpeta debe identificar datos sintéticos');
const targets = await json(`${prometheusUrl}/api/v1/targets`);
assert.equal(targets.data.activeTargets.length, 3);
for (const target of targets.data.activeTargets) {
  assert(target.scrapeUrl.startsWith('http://synthetic-metrics:8000/metrics/'), 'No se contacta Chatwoot real');
  assert.equal(target.health, 'up');
}
for (const { panel, query } of queries) {
  const expression = interpolate(query.expr);
  const values = await prom(expression);
  for (const value of values) assert(Number.isFinite(Number(value.value[1])), `${panel.title}: valor no finito`);
  await grafanaQuery(expression);
}
assert.equal(await number(selector('unal_chatwoot:slo_window_complete:bool30d')), 0);
summary.checks.push('Importación, datasource, todas las consultas y cobertura parcial');
console.log(`Importación y ${queries.length} consultas verificadas en Prometheus y Grafana.`);

const browser = await chromium.launch({ channel: process.env.VALIDATION_BROWSER_CHANNEL || 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 3600 }, deviceScaleFactor: 1 });
const browserErrors = [];
page.on('pageerror', error => browserErrors.push(error.message));
page.on('response', async response => {
  if (response.url().includes('/api/ds/query')) {
    if (!response.ok()) browserErrors.push(`Consulta HTTP ${response.status()}`);
    else {
      const body = await response.json();
      for (const result of Object.values(body.results || {})) if (result.error) browserErrors.push(result.error);
    }
  }
});

async function capture(name, expectedText) {
  await page.goto(`${grafanaUrl}/d/${uid}?orgId=1&var-project=devops-grupo7&var-environment=lab&from=now-5m&to=now`, { waitUntil: 'domcontentloaded' });
  await page.getByText('Disponibilidad · 30d · ≥99 %', { exact: true }).first().waitFor({ state: 'visible', timeout: 60000 });
  await page.getByText(expectedText, { exact: true }).last().waitFor({ state: 'visible', timeout: 60000 });
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  await page.screenshot({ path: resolve(outputDir, `synthetic-${name}.png`), fullPage: true, animations: 'disabled' });
  assert.deepEqual(browserErrors, [], 'Errores de navegador o consultas del dashboard');
}

try {
  await capture('healthy', 'HISTORIAL PARCIAL');
  summary.checks.push('Visualización inicial con historial parcial');
  console.log('Captura inicial sintética guardada.');

  await scenario('degraded');
  await waitFor('Degradación en los indicadores', async () => {
    const availability = await number(selector('unal_chatwoot:slo_sli:ratio', 'slo="availability",window="30d"'));
    const latency = await number(selector('unal_chatwoot:http_request_duration:p95_seconds', 'availability_result="good",window="5m"'));
    const budget = await number(selector('unal_chatwoot:slo_budget_remaining:ratio', 'slo="availability",window="30d"'));
    return availability !== null && availability < 0.99 && latency > 0.5 && budget < 0;
  });
  await capture('degraded', 'VÁLIDA');
  summary.checks.push('Degradación con 4xx bad, p95 superior al umbral y presupuesto negativo');
  console.log('Degradación y presupuesto negativo verificados.');

  await scenario('telemetry_missing');
  await waitFor('Métricas HTTP ausentes', async () => (await prom(selector('unal_chatwoot:slo_sli:ratio'))).length === 0);
  assert.equal(await number(selector('up', 'job="chatwoot-http"')), 1);
  const availabilityPanel = dashboard.panels.find(panel => panel.title.startsWith('Disponibilidad ·'));
  const missingFrames = await grafanaQuery(interpolate(availabilityPanel.targets[0].expr));
  assert(missingFrames.every(frame => frame.data.values.every(values => values.length === 0)), 'Grafana no debe conservar éxito sin métricas');
  await capture('telemetry-missing', 'INCOMPLETA');
  summary.checks.push('Endpoint accesible sin métricas: SLO no evaluable y telemetría incompleta');
  console.log('Pérdida de métricas verificada sin convertirla en éxito.');

  await scenario('no_memory_limit');
  await waitFor('Límite de Redis ausente', async () => (await prom(selector('unal_container_memory_limit_bytes', 'component="redis"'))).length === 0);
  const memoryPanel = dashboard.panels.find(panel => panel.title === 'Contenedores · configuración de límites');
  const memoryStatus = await prom(interpolate(memoryPanel.targets[0].expr));
  assert.equal(Number(memoryStatus.find(value => value.metric.component === 'redis').value[1]), 0);
  const saturationPanel = dashboard.panels.find(panel => panel.title === 'Contenedores · memoria respecto al límite finito');
  assert(!(await prom(interpolate(saturationPanel.targets[0].expr))).some(value => value.metric.component === 'redis'));
  await capture('no-memory-limit', 'SIN LÍMITE');
  summary.checks.push('Memoria observada sin límite: estado explícito y ausencia de porcentaje ficticio');
  console.log('Ausencia de límite de memoria verificada.');

  await scenario('dependencies_missing');
  await waitFor('Métricas de dependencias ausentes', async () => (await prom(selector('unal_dependency_probe_success'))).length === 0);
  const dependencyPanel = dashboard.panels.find(panel => panel.title === 'Dependencias · último sondeo');
  const dependencyFrames = await grafanaQuery(interpolate(dependencyPanel.targets[0].expr));
  assert(dependencyFrames.every(frame => frame.data.values.every(values => values.length === 0)));
  summary.checks.push('Dependencias sin métricas: ausencia de datos y no éxito artificial');
} finally {
  await scenario('healthy');
  await browser.close();
}
summary.browser = `Microsoft Edge / Playwright ${JSON.parse(await readFile(resolve(validationDir, 'node_modules/playwright/package.json'), 'utf8')).version}`;
summary.grafana = (await json(`${grafanaUrl}/api/health`)).version;
summary.prometheus = (await json(`${prometheusUrl}/api/v1/status/buildinfo`)).data.version;
summary.completedAt = new Date().toISOString();
await writeFile(resolve(outputDir, 'validation-results.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log('Validación del dashboard completada; generador restaurado a healthy.');
