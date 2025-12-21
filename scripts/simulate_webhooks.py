#!/usr/bin/env python3
"""
Simulate GitHub webhook events for local testing.

Usage:
    # Test against local API
    python scripts/simulate_webhooks.py --url http://localhost:8000

    # Test against deployed API
    python scripts/simulate_webhooks.py --url https://api.cicosts.dev

This simulates the complete flow:
1. Installation created event
2. Workflow run completed events
3. Workflow job completed events
"""
import argparse
import json
import requests
import random
from datetime import datetime, timedelta
from uuid import uuid4


def simulate_installation_created(base_url: str, org_id: int, org_login: str):
    """Simulate GitHub App installation event."""
    payload = {
        "event_type": "installation",
        "action": "created",
        "delivery_id": str(uuid4()),
        "payload": {
            "action": "created",
            "installation": {
                "id": random.randint(40000000, 50000000),
                "account": {
                    "id": org_id,
                    "login": org_login,
                    "type": "Organization",
                    "avatar_url": f"https://avatars.githubusercontent.com/u/{org_id}",
                },
                "repository_selection": "all",
                "app_id": 12345,
                "target_type": "Organization",
            },
            "sender": {
                "id": 12345,
                "login": "admin-user",
            },
        }
    }

    return send_webhook(base_url, payload)


def simulate_workflow_run(base_url: str, org_id: int, org_login: str,
                          installation_id: int, repo_name: str, workflow_name: str):
    """Simulate a completed workflow run event."""
    run_id = random.randint(10000000000, 99999999999)
    now = datetime.utcnow()
    created = now - timedelta(minutes=random.randint(5, 30))

    payload = {
        "event_type": "workflow_run",
        "action": "completed",
        "delivery_id": str(uuid4()),
        "payload": {
            "action": "completed",
            "workflow_run": {
                "id": run_id,
                "name": workflow_name,
                "run_number": random.randint(100, 999),
                "status": "completed",
                "conclusion": random.choice(["success", "success", "success", "failure"]),
                "event": random.choice(["push", "pull_request", "schedule"]),
                "actor": {"login": random.choice(["developer1", "developer2", "ci-bot"])},
                "created_at": created.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "head_branch": "main",
                "head_sha": uuid4().hex[:40],
            },
            "workflow": {
                "id": random.randint(1000000, 9999999),
                "name": workflow_name,
                "path": f".github/workflows/{workflow_name.lower().replace(' ', '-')}.yml",
            },
            "repository": {
                "id": random.randint(100000000, 999999999),
                "name": repo_name,
                "full_name": f"{org_login}/{repo_name}",
                "owner": {"id": org_id, "login": org_login},
            },
            "organization": {
                "id": org_id,
                "login": org_login,
            },
            "installation": {"id": installation_id},
            "sender": {"login": "github-actions[bot]"},
        }
    }

    return send_webhook(base_url, payload), run_id


def simulate_workflow_job(base_url: str, org_id: int, org_login: str,
                          installation_id: int, repo_name: str, run_id: int,
                          job_name: str, runner_type: str):
    """Simulate a completed workflow job event."""
    now = datetime.utcnow()
    started = now - timedelta(minutes=random.randint(1, 15))

    # Calculate cost based on runner type
    duration_mins = random.randint(1, 10)

    payload = {
        "event_type": "workflow_job",
        "action": "completed",
        "delivery_id": str(uuid4()),
        "payload": {
            "action": "completed",
            "workflow_job": {
                "id": random.randint(10000000000, 99999999999),
                "run_id": run_id,
                "name": job_name,
                "status": "completed",
                "conclusion": "success",
                "started_at": started.isoformat() + "Z",
                "completed_at": now.isoformat() + "Z",
                "labels": [runner_type],
                "runner_name": f"GitHub Actions {random.randint(1, 10)}",
                "runner_group_name": "Default",
            },
            "repository": {
                "id": random.randint(100000000, 999999999),
                "name": repo_name,
                "full_name": f"{org_login}/{repo_name}",
                "owner": {"id": org_id, "login": org_login},
            },
            "organization": {
                "id": org_id,
                "login": org_login,
            },
            "installation": {"id": installation_id},
            "sender": {"login": "github-actions[bot]"},
        }
    }

    return send_webhook(base_url, payload)


def send_webhook(base_url: str, payload: dict) -> dict:
    """Send a webhook payload to the API."""
    url = f"{base_url}/api/v1/webhooks/github"

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": payload["event_type"],
        "X-GitHub-Delivery": payload["delivery_id"],
        # Note: In development mode, signature verification is skipped
    }

    try:
        response = requests.post(url, json=payload["payload"], headers=headers, timeout=30)
        return {
            "status": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "event_type": payload["event_type"],
            "action": payload["action"],
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "event_type": payload["event_type"],
            "action": payload["action"],
        }


def run_full_simulation(base_url: str):
    """Run a complete simulation of webhook events."""
    print("=" * 60)
    print("CICosts Webhook Simulation")
    print("=" * 60)
    print(f"Target: {base_url}")
    print()

    # Test organization details
    org_id = 20001
    org_login = "acme-corp"
    installation_id = random.randint(40000000, 50000000)

    # Step 1: Simulate installation
    print("[1/3] Simulating GitHub App installation...")
    result = simulate_installation_created(base_url, org_id, org_login)
    print(f"      Status: {result['status']}")
    if result['status'] != 200:
        print(f"      Response: {result.get('response', result.get('error'))}")
    print()

    # Step 2: Simulate workflow runs
    print("[2/3] Simulating workflow runs...")
    repos = ["main-app", "frontend", "api-service"]
    workflows = ["CI Pipeline", "Deploy Production", "Tests"]
    run_ids = []

    for i, (repo, workflow) in enumerate(zip(repos, workflows)):
        result, run_id = simulate_workflow_run(
            base_url, org_id, org_login, installation_id, repo, workflow
        )
        run_ids.append((run_id, repo))
        print(f"      [{i+1}] {repo}/{workflow}: Status {result['status']}")
    print()

    # Step 3: Simulate jobs for each run
    print("[3/3] Simulating workflow jobs...")
    job_configs = [
        ("build", "ubuntu-latest"),
        ("test", "ubuntu-latest"),
        ("lint", "ubuntu-latest"),
        ("deploy", "ubuntu-latest-4-cores"),
    ]

    for run_id, repo in run_ids:
        for job_name, runner in job_configs[:random.randint(2, 4)]:
            result = simulate_workflow_job(
                base_url, org_id, org_login, installation_id,
                repo, run_id, job_name, runner
            )
            print(f"      {repo}/{job_name} ({runner}): Status {result['status']}")

    print()
    print("=" * 60)
    print("Simulation complete!")
    print()
    print("Next steps:")
    print("  1. Check the dashboard at http://localhost:3000/dashboard")
    print("  2. Or query the API: GET /api/v1/dashboard/summary?org_id=<uuid>")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Simulate GitHub webhooks for CICosts")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--event",
        choices=["installation", "workflow_run", "workflow_job", "all"],
        default="all",
        help="Type of event to simulate (default: all)"
    )

    args = parser.parse_args()

    if args.event == "all":
        run_full_simulation(args.url)
    else:
        print(f"Simulating single {args.event} event...")
        # Add single event simulation here if needed
        run_full_simulation(args.url)


if __name__ == "__main__":
    main()
