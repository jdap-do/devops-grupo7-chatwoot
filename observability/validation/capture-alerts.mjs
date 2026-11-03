// Capture the actual synthetic stack while at least one alert is firing.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const url = 'http://127.0.0.1:19090';
const response = await fetch(`${url}/api/v1/alerts`);
assert(response.ok);
const alerts = (await response.json()).data.alerts.filter(alert => alert.state === 'firing');
assert(alerts.length, 'Debe haber al menos una alerta activa para capturar la evidencia');
const output = new URL('../evidence/david/alerts/', import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto(`${url}/alerts`, { waitUntil: 'domcontentloaded' });
  await page.getByText(alerts[0].labels.alertname, { exact: true }).first().waitFor();
  await page.screenshot({ path: fileURLToPath(new URL('synthetic-alerts-firing.png', output)), fullPage: true });
  console.log('Captura sintética guardada:', alerts.map(alert => alert.labels.alertname).join(', '));
} finally {
  await browser.close();
}
