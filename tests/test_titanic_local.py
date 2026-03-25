#!/usr/bin/env python3
"""End-to-end Titanic Kaggle smoke check against a local backend."""

import json
import os
import sys
import time
import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("KAGGLE_SOLVER_URL", "http://localhost:8000")
QUERY = os.getenv(
    "TITANIC_LOCAL_QUERY",
    "Solve Titanic competition end to end",
)
ENV_FILE_CANDIDATES = [
    os.getenv("TITANIC_ENV_FILE", ""),
    ".env",
    "env",
]
HEALTH_TIMEOUT_SECONDS = int(os.getenv("TITANIC_HEALTH_TIMEOUT", "120"))
SESSION_TIMEOUT_SECONDS = int(os.getenv("TITANIC_SESSION_TIMEOUT", "360"))
DEBUG_LOGS = os.getenv("TITANIC_DEBUG", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}


def debug(message: str) -> None:
    if DEBUG_LOGS:
        print(f"[DEBUG] {message}")


def load_env_file() -> None:
    for candidate in ENV_FILE_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.exists() or not path.is_file():
            continue

        loaded_any = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if "=" not in stripped:
                known_prefixes = (
                    "KAGGLE_API_TOKEN",
                    "OPENROUTER_API_KEY",
                    "OPENAI_API_KEY",
                )
                for prefix in known_prefixes:
                    if stripped.startswith(prefix) and len(stripped) > len(prefix):
                        value = stripped[len(prefix) :].strip().strip('"').strip("'")
                        if value and prefix not in os.environ:
                            os.environ[prefix] = value
                            loaded_any = True
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key.startswith("KAGGLE_API_TOKEN") and key != "KAGGLE_API_TOKEN":
                if value and "KAGGLE_API_TOKEN" not in os.environ:
                    os.environ["KAGGLE_API_TOKEN"] = value
                    loaded_any = True
                continue

            if key and key not in os.environ:
                os.environ[key] = value
                loaded_any = True

        if loaded_any:
            return


def http_get(path: str) -> Dict[str, Any]:
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def http_put(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


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
        except Exception as exc:  # pragma: no cover
            last_error = str(exc)
        time.sleep(2)

    raise RuntimeError(
        f"Backend did not become healthy in time. Last error: {last_error}"
    )


def configure_tokens_from_env() -> None:
    llm_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

    kaggle_key = os.getenv("KAGGLE_API_TOKEN", "")
    kaggle_username = os.getenv("KAGGLE_USERNAME", "")
    kaggle_api_key = os.getenv("KAGGLE_API_KEY", "")

    if not kaggle_key and kaggle_username and kaggle_api_key:
        kaggle_key = f"{kaggle_username}:{kaggle_api_key}"

    payload: Dict[str, Any] = {}
    if llm_key:
        payload["api_key"] = llm_key
    if kaggle_key:
        payload["kaggle_key"] = kaggle_key

    if payload:
        http_put("/api/settings", payload)


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
                data = event.get("data", {})
                if event_type == "tool":
                    debug(
                        "SSE tool event "
                        f"tool_name={data.get('tool_name')} "
                        f"success={data.get('success', 'unknown')}"
                    )
                else:
                    debug(f"SSE event: {event_type}")

            if event_type == "session_done":
                return event.get("status", "unknown")

    return "unknown"


def flatten_file_paths(tree: List[Dict[str, Any]]) -> List[str]:
    paths: List[str] = []
    for node in tree:
        node_type = node.get("type")
        if node_type == "file":
            p = node.get("path")
            if isinstance(p, str):
                paths.append(p)
        elif node_type == "folder":
            paths.extend(flatten_file_paths(node.get("children", [])))
    return paths


def extract_tool_names(events: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for event in events:
        if event.get("type") != "tool":
            continue
        data = event.get("data", {})
        tool_name = data.get("tool_name")
        if isinstance(tool_name, str):
            names.append(tool_name)
    return names


def extract_tool_sequence(events: List[Dict[str, Any]]) -> List[str]:
    return extract_tool_names(events)


def extract_kaggle_tool_errors(events: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    fallback_pattern = re.compile(r"\"?success\"?\s*[:=]\s*false", re.IGNORECASE)

    for event in events:
        if event.get("type") != "tool":
            continue
        data = event.get("data", {})
        tool_name = data.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.startswith("kaggle_"):
            continue

        output_text = str(data.get("output", ""))
        parsed: Any = None
        failure_detected = False
        try:
            parsed = json.loads(output_text)
        except Exception:
            try:
                parsed = ast.literal_eval(output_text)
            except Exception:
                parsed = None

        if isinstance(parsed, dict) and "success" in parsed:
            success_value = parsed.get("success")
            is_failure = success_value is False
            if isinstance(success_value, str):
                is_failure = success_value.strip().lower() == "false"
            if is_failure:
                err = parsed.get("error") or "unknown kaggle tool error"
                errors.append(f"{tool_name}: {err}")
                failure_detected = True

        if not failure_detected and fallback_pattern.search(output_text):
            errors.append(f"{tool_name}: {output_text[:300]}")

    return errors


def find_stage_file_paths(all_paths: List[str]) -> Dict[str, str]:
    expected_names = [
        "titanic_data/train.csv",
        "titanic_data/test.csv",
        "titanic_data/sample_submission.csv",
        "submission.csv",
    ]
    result: Dict[str, str] = {}
    for path in all_paths:
        normalized = path.replace("\\", "/")
        for expected in expected_names:
            if normalized.endswith(expected):
                result[expected] = path
    return result


def assert_tool_order(tool_sequence: List[str]) -> None:
    required_stages = ["kaggle_download_data", "kaggle_submit"]
    indices: Dict[str, int] = {}
    for idx, tool in enumerate(tool_sequence):
        if tool not in indices:
            indices[tool] = idx

    missing = [stage for stage in required_stages if stage not in indices]
    if missing:
        raise RuntimeError(
            f"Missing required Kaggle stage(s): {missing}. Tool sequence: {tool_sequence}"
        )

    if indices["kaggle_download_data"] >= indices["kaggle_submit"]:
        raise RuntimeError(
            "Unexpected tool order: kaggle_submit happened before kaggle_download_data. "
            f"Tool sequence: {tool_sequence}"
        )


def summarize_errors(events: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for event in events[-40:]:
        event_type = event.get("type")
        if event_type not in {"tool", "error", "result"}:
            continue
        data = event.get("data", {})
        if event_type == "tool":
            output = str(data.get("output", ""))
            if "error" in output.lower() or "not found" in output.lower():
                lines.append(f"tool={data.get('tool_name')}: {output[:200]}")
        elif event_type == "error":
            lines.append(str(data.get("content", data))[:200])
    return " | ".join(lines) if lines else "no explicit errors in last events"


def main() -> int:
    print(f"Using backend: {BASE_URL}")
    print(f"Submitting query: {QUERY}")
    debug(
        f"Timeouts: health={HEALTH_TIMEOUT_SECONDS}s session={SESSION_TIMEOUT_SECONDS}s"
    )

    load_env_file()
    wait_for_health()
    configure_tokens_from_env()

    query_response = http_post("/api/query", {"query": QUERY})
    session_id = query_response.get("session_id")
    if not session_id:
        raise RuntimeError(f"No session_id in response: {query_response}")

    print(f"Session started: {session_id}")
    debug("Waiting for session completion via SSE")

    stream_status = stream_sse_until_done(session_id)
    session_data = http_get(f"/api/session/{session_id}")
    status = session_data.get("status", stream_status)

    events = session_data.get("events", [])
    debug(f"Collected events: {len(events)}")
    if status != "completed":
        artifacts = session_data.get("artifacts", {})
        err = artifacts.get("error", "unknown error")
        raise RuntimeError(
            f"Session ended with status '{status}': {err}. Diagnostics: {summarize_errors(events)}"
        )

    tool_names = extract_tool_names(events)
    tool_sequence = extract_tool_sequence(events)
    debug(f"Tool sequence: {tool_sequence}")
    assert_tool_order(tool_sequence)

    if "kaggle_validate_submission" not in tool_names:
        debug(
            "kaggle_validate_submission not detected; continuing with file-level checks"
        )

    kaggle_errors = extract_kaggle_tool_errors(events)
    if kaggle_errors:
        raise RuntimeError("Kaggle tool execution failed. " + " | ".join(kaggle_errors))

    files_data = http_get(
        f"/api/workspace/files?session_id={urllib.parse.quote(session_id)}"
    )
    all_paths = flatten_file_paths(files_data.get("files", []))
    debug(f"Workspace file count: {len(all_paths)}")
    stage_paths = find_stage_file_paths(all_paths)
    titanic_paths = [p for p in all_paths if "titanic_data" in p]

    required_stage_files = [
        "titanic_data/train.csv",
        "titanic_data/test.csv",
        "titanic_data/sample_submission.csv",
        "submission.csv",
    ]
    missing_stage_files = [
        item for item in required_stage_files if item not in stage_paths
    ]
    if missing_stage_files:
        raise RuntimeError(
            "Missing expected stage artifacts: "
            f"{missing_stage_files}. Detected paths: {sorted(stage_paths.values())}"
        )

    if not titanic_paths:
        raise RuntimeError(
            "Kaggle tools ran but no downloaded titanic_data files were found. "
            f"Workspace files: {all_paths}"
        )

    submission_path = stage_paths["submission.csv"]
    submission_data = http_get(
        f"/api/workspace/read?path={urllib.parse.quote(submission_path)}"
    )
    submission_content = submission_data.get("content", "")
    debug(
        f"Submission path: {submission_path}; first 120 chars: "
        f"{submission_content[:120]!r}"
    )
    lines = [line for line in submission_content.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(
            f"submission.csv appears empty or header-only: {submission_path}"
        )
    header = lines[0].replace(" ", "")
    if header.lower() != "passengerid,survived":
        raise RuntimeError(
            "submission.csv has unexpected header. "
            f"Expected 'PassengerId,Survived', got: {lines[0]!r}"
        )

    print("Success: Titanic local integration run completed")
    print(f"Session: {session_id}")
    print(f"Detected Kaggle tool calls: {sorted(set(tool_names))}")
    print(f"Downloaded paths count: {len(titanic_paths)}")
    print(f"Submission rows (including header): {len(lines)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
