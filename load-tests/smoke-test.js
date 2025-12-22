import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const healthDuration = new Trend('health_duration');
const summaryDuration = new Trend('summary_duration');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://dev-api.cicosts.dev';
const ORG_ID = __ENV.ORG_ID || '092a5e97-9c62-40fc-aadc-0c4a32bf5646';

export const options = {
  vus: 1,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
};

export default function () {
  // Test 1: Health check
  const healthRes = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: 'health' },
  });

  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'health response has status': (r) => {
      const body = JSON.parse(r.body);
      return body.status === 'ok' || body.status === 'degraded';
    },
  }) || errorRate.add(1);

  healthDuration.add(healthRes.timings.duration);

  sleep(1);

  // Test 2: Dashboard summary (unauthenticated - should return 401)
  // Use expectedStatuses to tell k6 that 401 is not a failure
  const summaryRes = http.get(`${BASE_URL}/api/v1/dashboard/summary?org_id=${ORG_ID}`, {
    tags: { endpoint: 'summary' },
    responseType: 'text',
    responseCallback: http.expectedStatuses(401),
  });

  // 401 is expected without auth - don't count as error
  const summaryOk = check(summaryRes, {
    'summary requires auth (401)': (r) => r.status === 401,
  });
  if (!summaryOk && summaryRes.status !== 401) {
    errorRate.add(1);
  }

  summaryDuration.add(summaryRes.timings.duration);

  sleep(1);

  // Test 3: API docs endpoint
  const docsRes = http.get(`${BASE_URL}/docs`, {
    tags: { endpoint: 'docs' },
  });

  check(docsRes, {
    'docs endpoint accessible': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(1);
}

export function handleSummary(data) {
  console.log('\n=== Smoke Test Summary ===\n');
  console.log(`Total requests: ${data.metrics.http_reqs.values.count}`);
  console.log(`Failed requests: ${data.metrics.http_req_failed.values.passes}`);
  console.log(`Avg response time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
  console.log(`95th percentile: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
  console.log(`Max response time: ${data.metrics.http_req_duration.values.max.toFixed(2)}ms`);

  return {
    stdout: JSON.stringify(data, null, 2),
  };
}
