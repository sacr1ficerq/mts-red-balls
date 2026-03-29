#!/usr/bin/env python3
"""End-to-end hello-world check against dockerized backend."""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("KAGGLE_SOLVER_URL", "http://localhost:8000")
QUERY = os.getenv("HELLO_WORLD_QUERY", "write hello world in rust")
HEALTH_TIMEOUT_SECONDS = int(os.getenv("HELLO_WORLD_HEALTH_TIMEOUT", "90"))
SESSION_TIMEOUT_SECONDS = int(os.getenv("HELLO_WORLD_SESSION_TIMEOUT", "240"))


def http_get(path: str) -> Dict[str, Any]:
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def stream_sse_until_done(session_id: str) -> str:
    req = urllib.request.Request(f"{BASE_URL}/api/sse/{session_id}", method="GET")
    with urllib.request.urlopen(req, timeout=SESSION_TIMEOUT_SECONDS + 30) as response:
        while True:
            line = response.readline()
            if not line:
                break

            decoded = line.decode("utf-8").strip()
            if not decoded.startswith("data: "):
                continue

            payload = decoded[len("data: ") :]
            if not payload:
                continue

            event = json.loads(payload)
            event_type = event.get("type")
            if event_type:
                print(f"SSE event: {event_type}")

            if event_type == "session_done":
                return event.get("status", "unknown")

    return "unknown"


def wait_for_health() -> None:
    deadline = time.time() + HEALTH_TIMEOUT_SECONDS
    last_error = "unknown"

    while time.time() < deadline:
        try:
            health = http_get("/api/health")
            if health.get("status") in {"healthy", "degraded"}:
                print(f"Backend is up: {health.get('status')}")
                return
        except urllib.error.URLError as exc:
            last_error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive path
            last_error = str(exc)

        time.sleep(2)

    raise RuntimeError(
        f"Backend did not become healthy in time. Last error: {last_error}"
    )


def find_first_rust_file(tree: List[Dict[str, Any]]) -> Optional[str]:
    for node in tree:
        if node.get("type") == "file" and str(node.get("path", "")).endswith(".rs"):
            return node["path"]

        if node.get("type") == "folder":
            found = find_first_rust_file(node.get("children", []))
            if found:
                return found

    return None


def main() -> int:
    print(f"Using backend: {BASE_URL}")
    print(f"Submitting query: {QUERY}")

    wait_for_health()

    query_response = http_post("/api/query", {"query": QUERY})
    session_id = query_response.get("session_id")
    if not session_id:
        raise RuntimeError(f"No session_id in response: {query_response}")

    print(f"Session started: {session_id}")

    status = stream_sse_until_done(session_id)
    session_data = http_get(f"/api/session/{session_id}")

    if not session_data:
        raise RuntimeError("Failed to fetch session data")

    status = session_data.get("status", status)
    if status != "completed":
        artifacts = session_data.get("artifacts", {})
        error = artifacts.get("error", "unknown error")
        raise RuntimeError(f"Session ended with status '{status}': {error}")

    files_data = http_get(
        f"/api/workspace/files?session_id={urllib.parse.quote(session_id)}"
    )
    rust_file = find_first_rust_file(files_data.get("files", []))
    if not rust_file:
        raise RuntimeError(
            "No .rs file found in session workspace. "
            f"Workspace tree: {files_data.get('files', [])}"
        )

    read_data = http_get(f"/api/workspace/read?path={urllib.parse.quote(rust_file)}")
    content = read_data.get("content", "")
    lowered = content.lower()
    if "hello" not in lowered or "world" not in lowered:
        raise RuntimeError(f"Rust file found but content is unexpected: {rust_file}")

    print(f"Success: generated Rust file '{rust_file}' with hello world content")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
