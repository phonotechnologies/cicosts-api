# CICosts API Load Tests

Performance testing suite using [k6](https://k6.io/).

## Prerequisites

Install k6:
```bash
brew install k6
```

## Test Types

| Test | Purpose | Duration | Peak VUs |
|------|---------|----------|----------|
| `smoke-test.js` | Verify endpoints work | 30s | 1 |
| `load-test.js` | Normal load simulation | 8min | 20 |
| `stress-test.js` | Find breaking point | 17min | 150 |

## Running Tests

### Smoke Test (Quick Validation)
```bash
k6 run smoke-test.js
```

### Load Test (Normal Traffic)
```bash
# Against dev
k6 run load-test.js

# Against prod (be careful!)
k6 run -e BASE_URL=https://api.cicosts.dev load-test.js
```

### Stress Test (Find Limits)
```bash
k6 run stress-test.js
```

### With Authentication
```bash
k6 run -e AUTH_TOKEN=your-jwt-token load-test.js
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `https://dev-api.cicosts.dev` | API base URL |
| `ORG_ID` | `092a5e97-9c62-40fc-aadc-0c4a32bf5646` | Test org ID |
| `AUTH_TOKEN` | (empty) | JWT token for authenticated tests |

## Thresholds

### Smoke Test
- P95 response time < 500ms
- Error rate < 1%

### Load Test
- P95 response time < 500ms
- P99 response time < 1000ms
- Error rate < 15% (accounts for Lambda throttling in dev)

### Stress Test
- P95 response time < 2000ms
- P99 response time < 5000ms
- Error rate < 10%

## Baseline Results (Dec 2025)

### Dev Environment (dev-api.cicosts.dev)

#### Smoke Test Results
| Metric | Value |
|--------|-------|
| Total Requests | 30 |
| Error Rate | 0% |
| Avg Duration | 101.62ms |
| P95 Duration | 181.45ms |
| Max Duration | 205.02ms |

#### Load Test Results (20 VUs, 8 min)
| Metric | Value |
|--------|-------|
| Total Requests | 12,485 |
| Error Rate | 12.45% |
| Avg Duration | 81.41ms |
| P95 Duration | 168.20ms |
| Max Duration | 1,675ms |

**Notes:**
- Error rate is primarily from Lambda throttling (503 responses) under sustained load
- Dev environment has limited Lambda concurrency
- Production environment expected to have lower error rate

## Interpreting Results

### Key Metrics
- **http_req_duration**: Response time (lower is better)
- **http_req_failed**: Failed request rate (lower is better)
- **http_reqs**: Requests per second throughput

### P95 Guidelines
| Endpoint | Target | Warning | Critical |
|----------|--------|---------|----------|
| `/health` | <100ms | <200ms | >500ms |
| `/api/v1/dashboard/summary` | <300ms | <500ms | >1000ms |
| `/api/v1/dashboard/trends` | <500ms | <800ms | >1500ms |
| `/api/v1/dashboard/workflows` | <500ms | <800ms | >1500ms |

## Output

Test results are saved to JSON files:
- `load-test-results.json`
- `stress-test-results.json`

## CI Integration

Add to GitHub Actions:
```yaml
- name: Run Load Tests
  run: |
    k6 run load-tests/smoke-test.js
```

## Notes

- Always test against dev first
- Rate limiting may affect results (60/min free, 300/min pro)
- Lambda cold starts can spike initial response times
- Database connection pooling affects sustained load
