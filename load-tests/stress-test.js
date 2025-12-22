import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency', true);

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://dev-api.cicosts.dev';
const ORG_ID = __ENV.ORG_ID || '092a5e97-9c62-40fc-aadc-0c4a32bf5646';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '3m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '3m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 150 },  // Ramp up to 150 users (stress point)
    { duration: '3m', target: 150 },  // Stay at 150 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    // Relaxed thresholds for stress testing - we expect some degradation
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    http_req_failed: ['rate<0.10'],  // Allow up to 10% failure under stress
    errors: ['rate<0.10'],
  },
};

export default function () {
  // Health check - lightweight, always test
  group('Health', () => {
    const res = http.get(`${BASE_URL}/health`, {
      tags: { endpoint: 'health' },
      timeout: '10s',
    });

    check(res, {
      'health ok': (r) => r.status === 200,
    }) || errorRate.add(1);
  });

  sleep(0.3);

  // API endpoints - heavier load
  group('API Load', () => {
    // Summary endpoint
    const summaryRes = http.get(
      `${BASE_URL}/api/v1/dashboard/summary?org_id=${ORG_ID}`,
      { tags: { endpoint: 'summary' }, timeout: '30s' }
    );

    check(summaryRes, {
      'summary responds': (r) => r.status === 200 || r.status === 401 || r.status === 429,
    }) || errorRate.add(1);

    apiLatency.add(summaryRes.timings.duration);

    // Trends endpoint - database intensive
    const trendsRes = http.get(
      `${BASE_URL}/api/v1/dashboard/trends?org_id=${ORG_ID}&days=30`,
      { tags: { endpoint: 'trends' }, timeout: '30s' }
    );

    check(trendsRes, {
      'trends responds': (r) => r.status === 200 || r.status === 401 || r.status === 429,
    }) || errorRate.add(1);

    apiLatency.add(trendsRes.timings.duration);

    // Workflows endpoint - heavy query
    const workflowsRes = http.get(
      `${BASE_URL}/api/v1/dashboard/workflows?org_id=${ORG_ID}&days=30`,
      { tags: { endpoint: 'workflows' }, timeout: '30s' }
    );

    check(workflowsRes, {
      'workflows responds': (r) => r.status === 200 || r.status === 401 || r.status === 429,
    }) || errorRate.add(1);

    apiLatency.add(workflowsRes.timings.duration);
  });

  sleep(0.5);
}

export function handleSummary(data) {
  const summary = {
    test: 'stress',
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
    breakdown: {
      healthP95: data.metrics['http_req_duration{endpoint:health}']?.values?.['p(95)']?.toFixed(2) || 'N/A',
      summaryP95: data.metrics['http_req_duration{endpoint:summary}']?.values?.['p(95)']?.toFixed(2) || 'N/A',
      trendsP95: data.metrics['http_req_duration{endpoint:trends}']?.values?.['p(95)']?.toFixed(2) || 'N/A',
      workflowsP95: data.metrics['http_req_duration{endpoint:workflows}']?.values?.['p(95)']?.toFixed(2) || 'N/A',
    },
  };

  console.log('\n========================================');
  console.log('        STRESS TEST RESULTS');
  console.log('========================================\n');
  console.log(`Environment: ${summary.environment}`);
  console.log(`Peak VUs: 150`);
  console.log(`Duration: ~17 minutes\n`);
  console.log('--- Overall Metrics ---');
  console.log(`Total Requests:    ${summary.metrics.totalRequests}`);
  console.log(`Failed Requests:   ${summary.metrics.failedRequests}`);
  console.log(`Error Rate:        ${summary.metrics.errorRate}`);
  console.log(`Avg Duration:      ${summary.metrics.avgDuration}ms`);
  console.log(`P95 Duration:      ${summary.metrics.p95Duration}ms`);
  console.log(`P99 Duration:      ${summary.metrics.p99Duration}ms`);
  console.log(`Max Duration:      ${summary.metrics.maxDuration}ms`);
  console.log('\n--- Endpoint Breakdown (P95) ---');
  console.log(`Health:     ${summary.breakdown.healthP95}ms`);
  console.log(`Summary:    ${summary.breakdown.summaryP95}ms`);
  console.log(`Trends:     ${summary.breakdown.trendsP95}ms`);
  console.log(`Workflows:  ${summary.breakdown.workflowsP95}ms`);
  console.log('\n========================================\n');

  return {
    'stress-test-results.json': JSON.stringify(summary, null, 2),
  };
}
