// Load test configuration
export const config = {
  // Environment URLs
  environments: {
    dev: 'https://dev-api.cicosts.dev',
    prod: 'https://api.cicosts.dev',
  },

  // Test organization ID (from phonotechnologies)
  testOrgId: '092a5e97-9c62-40fc-aadc-0c4a32bf5646',

  // Thresholds for pass/fail
  thresholds: {
    // 95th percentile response time < 500ms
    http_req_duration: ['p(95)<500'],
    // Error rate < 1%
    http_req_failed: ['rate<0.01'],
    // 99th percentile < 1s
    'http_req_duration{endpoint:health}': ['p(99)<200'],
    'http_req_duration{endpoint:summary}': ['p(95)<500'],
    'http_req_duration{endpoint:trends}': ['p(95)<800'],
  },

  // Load profiles
  profiles: {
    smoke: {
      vus: 1,
      duration: '30s',
    },
    load: {
      stages: [
        { duration: '1m', target: 10 },   // Ramp up
        { duration: '3m', target: 10 },   // Steady state
        { duration: '1m', target: 0 },    // Ramp down
      ],
    },
    stress: {
      stages: [
        { duration: '1m', target: 20 },
        { duration: '2m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '1m', target: 0 },
      ],
    },
    spike: {
      stages: [
        { duration: '30s', target: 5 },
        { duration: '10s', target: 100 },  // Spike!
        { duration: '30s', target: 5 },
        { duration: '30s', target: 0 },
      ],
    },
  },
};
