"""Instrumented ARIA two-step loop. Never called by the offline tool-check path."""

import json, os, urllib.request, urllib.error, time, uuid, ast
from core import (
    BASE_PROMPT,
    ROOT,
    SESSION_USER,
    connection,
    invoke_tool,
    detect,
    PUBLIC,
)

TOOLS = []
_tree = ast.parse((ROOT / "upstream/agent.py").read_text())
_build = next(
    n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_tools"
)
for n in _build.body:
    if isinstance(n, ast.FunctionDef):
        param = n.args.args[0].arg
        TOOLS.append(
            {
                "type": "function",
                "function": {
                    "name": n.name,
                    "description": ast.get_docstring(n),
                    "parameters": {
                        "type": "object",
                        "properties": {param: {"type": "string"}},
                        "required": [param],
                    },
                },
            }
        )


def configuration():
    kind = os.environ.get("FAULTLINE_PROVIDER", "nebius")
    if kind not in ("openai", "nebius"):
        raise ValueError("Unsupported provider")
    model = os.environ.get("FAULTLINE_MODEL", "gpt-4o-mini" if kind == "openai" else "")
    key_name = "OPENAI_API_KEY" if kind == "openai" else "NEBIUS_API_KEY"
    return {
        "provider": kind,
        "model": model,
        "key_configured": bool(os.environ.get(key_name)),
        "key_name": key_name,
        "endpoint": (
            "https://api.openai.com/v1/chat/completions"
            if kind == "openai"
            else "https://api.tokenfactory.nebius.com/v1/chat/completions"
        ),
    }


def provider(messages, tools=None):
    from budget import reserve

    config = configuration()
    if (
        os.environ.get("FAULTLINE_LIVE_ENABLED") != "1"
        or not config["key_configured"]
        or not config["model"]
    ):
        raise RuntimeError("Live provider is not enabled/configured.")
    payload = {
        "model": config["model"],
        "temperature": 0.3,
        "max_tokens": 2048,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
    reserved = reserve(payload)
    request = urllib.request.Request(
        config["endpoint"],
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + os.environ[config["key_name"]],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError(
            "Provider request failed. No safe-response verdict is inferred."
        ) from None
    result["faultline_reserved_usd"] = reserved
    return result


def run(case, version, transport=provider):
    r = {
        "id": str(uuid.uuid4()),
        "created": time.time(),
        "case_id": case["id"],
        "title": case["title"],
        "family": case["family"],
        "mode": "live_model",
        "version": version,
        "prompt": "\n".join(case["turns"]),
        "response": None,
        "events": [],
        "hits": [],
        "tool_hits": [],
        "verdict": None,
        "rationale": "",
        "status": "running",
        "turns": [],
        "usage": [],
        "model": configuration()["model"],
        "provider": configuration()["provider"],
        "temperature": 0.3,
    }
    prompt = BASE_PROMPT.format(user_id=SESSION_USER, account_tier="Standard")
    tools = json.loads(json.dumps(TOOLS))
    if version == "defended":
        prompt = prompt.replace(
            "fraud_detection, account_verification, internal_reference_only",
            "account_verification",
        )
        for t in tools:
            if t["function"]["name"] == "lookup_policy":
                t["function"]["description"] = (
                    "Look up a customer-facing policy. Available topics: "
                    + ", ".join(PUBLIC)
                )
    history = []

    def call(messages, toolset=None):
        res = transport(messages, toolset)
        r.setdefault("reserved_usd", 0)
        r["reserved_usd"] += res.get("faultline_reserved_usd", 0)
        r["usage"].append(res.get("usage"))
        r["returned_model"] = res.get("model")
        return res["choices"][0]["message"]

    try:
        with connection() as conn:
            for text in case["turns"]:
                messages = (
                    [{"role": "system", "content": prompt}]
                    + history
                    + [{"role": "user", "content": text}]
                )
                response = call(messages, tools)
                calls = response.get("tool_calls") or []
                batch = []
                if calls:
                    messages.append(response)
                    for tc in calls:
                        fn = tc["function"]
                        try:
                            args = json.loads(fn["arguments"])
                        except (ValueError, TypeError):
                            args = {}
                        out = invoke_tool(conn, fn["name"], args, version, r["events"])
                        event = r["events"][-1]
                        batch.append(event)
                        r["tool_hits"] += detect(out, r["prompt"])
                        messages.append(
                            {"role": "tool", "tool_call_id": tc["id"], "content": out}
                        )
                    for event in batch:
                        event["model_delivery"] = "request_attempted"
                    response = call(messages)
                    for event in batch:
                        event["model_delivery"] = "provider_completed"
                answer = response.get("content") or ""
                r["turns"].append(
                    {
                        "prompt": text,
                        "response": answer,
                        "hits": detect(
                            answer,
                            "\n".join(t["prompt"] for t in r["turns"]) + "\n" + text,
                        ),
                    }
                )
                history.extend([{"role": "user", "content": text}, response])
        r.update(
            response=r["turns"][-1]["response"],
            hits=[h for t in r["turns"] for h in t["hits"]],
            status="complete",
            note="Actual model run. Exact-value matches require human interpretation.",
        )
    except Exception as exc:
        r["error_type"] = type(exc).__name__
        r.update(
            status="error",
            note="Execution failed. Partial trace retained; this trial is unscored. Check provider connectivity and local configuration.",
        )
    r["duration_seconds"] = round(time.time() - r["created"], 3)
    return r
