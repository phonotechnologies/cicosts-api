import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const healthCheck = new Trend('health_check_duration', true);
const apiLatency = new Trend('api_latency', true);
const requestCount = new Counter('total_requests');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://dev-api.cicosts.dev';
const ORG_ID = __ENV.ORG_ID || '092a5e97-9c62-40fc-aadc-0c4a32bf5646';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up to 10 users
    { duration: '3m', target: 10 },   // Stay at 10 users
    { duration: '1m', target: 20 },   // Ramp up to 20 users
    { duration: '2m', target: 20 },   // Stay at 20 users
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    // Allow up to 15% errors during load testing (dev Lambda throttling expected)
    errors: ['rate<0.15'],
    'health_check_duration': ['p(95)<300'],  // Allow for Lambda cold starts
    'api_latency': ['p(95)<500'],
  },
};

const headers = AUTH_TOKEN ? {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json',
} : {
  'Content-Type': 'application/json',
};

export default function () {
  // Group 1: Health endpoints
  group('Health Checks', () => {
    const res = http.get(`${BASE_URL}/health`, {
      tags: { endpoint: 'health', type: 'health' },
    });

    const healthOk = check(res, {
      'health is 200': (r) => r.status === 200,
    });
    errorRate.add(!healthOk);

    healthCheck.add(res.timings.duration);
    requestCount.add(1);
  });

  sleep(0.5);

  // Group 2: Public endpoints
  group('Public Endpoints', () => {
    // OpenAPI docs
    const docsRes = http.get(`${BASE_URL}/openapi.json`, {
      tags: { endpoint: 'openapi', type: 'public' },
    });

    const docsOk = check(docsRes, {
      'openapi accessible': (r) => r.status === 200,
    });
    errorRate.add(!docsOk);

    apiLatency.add(docsRes.timings.duration);
    requestCount.add(1);
  });

  sleep(0.5);

  // Group 3: API endpoints (authentication test)
  group('API Endpoints', () => {
    const expectedStatus = AUTH_TOKEN ? 200 : 401;
    // When running without auth, tell k6 that 401/429/503 are expected (not failures)
    // 401 = unauthorized (expected), 429 = rate limited, 503 = Lambda throttling
    const expectedStatuses = AUTH_TOKEN
      ? http.expectedStatuses(200)
      : http.expectedStatuses(401, 429, 503);

    // Valid responses for checks: expected status OR throttling
    const isValidResponse = (r) =>
      r.status === expectedStatus || r.status === 429 || r.status === 503;

    // Dashboard summary - tests auth and database
    const summaryRes = http.get(
      `${BASE_URL}/api/v1/dashboard/summary?org_id=${ORG_ID}`,
      {
        headers,
        tags: { endpoint: 'summary', type: 'api' },
        responseCallback: expectedStatuses,
      }
    );

    const summaryOk = check(summaryRes, {
      'summary responds correctly': isValidResponse,
    });
    errorRate.add(!summaryOk);  // Add 1 for failure, 0 for success

    apiLatency.add(summaryRes.timings.duration);
    requestCount.add(1);

    // Dashboard trends
    const trendsRes = http.get(
      `${BASE_URL}/api/v1/dashboard/trends?org_id=${ORG_ID}&days=30`,
      {
        headers,
        tags: { endpoint: 'trends', type: 'api' },
        responseCallback: expectedStatuses,
      }
    );

    const trendsOk = check(trendsRes, {
      'trends responds correctly': isValidResponse,
    });
    errorRate.add(!trendsOk);

    apiLatency.add(trendsRes.timings.duration);
    requestCount.add(1);

    // Top workflows
    const topRes = http.get(
      `${BASE_URL}/api/v1/dashboard/top-workflows?org_id=${ORG_ID}&days=30&limit=5`,
      {
        headers,
        tags: { endpoint: 'top-workflows', type: 'api' },
        responseCallback: expectedStatuses,
      }
    );

    const topOk = check(topRes, {
      'top-workflows responds correctly': isValidResponse,
    });
    errorRate.add(!topOk);

    apiLatency.add(topRes.timings.duration);
    requestCount.add(1);
  });

  sleep(1);
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    environment: BASE_URL,
    metrics: {
      totalRequests: data.metrics.http_reqs?.values?.count || 0,
      failedRequests: data.metrics.http_req_failed?.values?.passes || 0,
      avgDuration: data.metrics.http_req_duration?.values?.avg?.toFixed(2) || 0,
      p95Duration: data.metrics.http_req_duration?.values?.['p(95)']?.toFixed(2) || 0,
      p99Duration: data.metrics.http_req_duration?.values?.['p(99)']?.toFixed(2) || 0,
      maxDuration: data.metrics.http_req_duration?.values?.max?.toFixed(2) || 0,
      errorRate: ((data.metrics.errors?.values?.rate || 0) * 100).toFixed(2) + '%',
    },
    thresholds: data.thresholds || {},
  };

  console.log('\n========================================');
  console.log('        LOAD TEST RESULTS');
  console.log('========================================\n');
  console.log(`Environment: ${summary.environment}`);
  console.log(`Timestamp: ${summary.timestamp}\n`);
  console.log('--- Metrics ---');
  console.log(`Total Requests:    ${summary.metrics.totalRequests}`);
  console.log(`Failed Requests:   ${summary.metrics.failedRequests}`);
  console.log(`Error Rate:        ${summary.metrics.errorRate}`);
  console.log(`Avg Duration:      ${summary.metrics.avgDuration}ms`);
  console.log(`P95 Duration:      ${summary.metrics.p95Duration}ms`);
  console.log(`P99 Duration:      ${summary.metrics.p99Duration}ms`);
  console.log(`Max Duration:      ${summary.metrics.maxDuration}ms`);
  console.log('\n========================================\n');

  return {
    'load-test-results.json': JSON.stringify(summary, null, 2),
  };
}
