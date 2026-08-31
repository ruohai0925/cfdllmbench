#!/usr/bin/env python3
"""claude_bridge.py -- an OpenAI-compatible endpoint in front of the Claude Code CLI,
so Foam-Agent can be driven by a Claude subscription without changing its source.

    python tools/claude_bridge.py &                       # 127.0.0.1:8787
    python tools/run_benchmarks.py --backend claude ...   # points Foam-Agent here

Foam-Agent picks its backend from `model_provider` (src/utils.py). Its `anthropic`
branch builds a ChatAnthropic, which wants an ANTHROPIC_API_KEY -- metered API access,
not the subscription. The seam that needs no source change is the `openai` branch:
it goes through ChatOpenAI, which honours OPENAI_BASE_URL. Point that at this process
and every one of Foam-Agent's ~22 call sites lands on POST /v1/chat/completions here,
where it is turned into one stateless `claude -p` call.

    Foam-Agent (unmodified)                this bridge                  Claude subscription
      LLMService.invoke                     flatten messages
      provider=openai   ---- HTTP ---->     claude -p --model ... ----> Claude Code CLI
      OPENAI_BASE_URL=here                  wrap answer as OpenAI JSON

Two request shapes, because LLMService has two:
- plain text  -> the CLI's answer becomes message.content.
- structured  -> langchain's .with_structured_output() sends the pydantic schema as an
  OpenAI `tool`; we append "answer with only JSON matching this schema", pull the JSON
  out of the reply and hand it back as a tool_call, which langchain parses into the
  pydantic object. Bad JSON is retried twice before the call is failed.

No API key is used or needed: authentication is whatever `claude` itself is signed in
with. ANTHROPIC_API_KEY is dropped from the child environment so a subscription run
cannot silently turn into a metered one, and so are the CLAUDE_CODE_* variables of a
parent Claude Code session, which would otherwise make the child think it is a subagent.

Derived from the claude-bridge prototype written for cfdqanda-platform (validated there
end-to-end on Foam-Agent, 2026-07-31); this copy adds --effort, JSON output parsing,
usage-limit reporting and stdin prompts.
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")   # loopback: this is a local sidecar
PORT = int(os.environ.get("BRIDGE_PORT", "8787"))
CLAUDE_BIN = os.environ.get("BRIDGE_CLAUDE_BIN", "claude")
# Model and effort the benchmark is to be run with. `claude-opus-5` is the full name;
# the alias `opus` would silently follow whatever the CLI currently calls latest.
CLAUDE_MODEL = os.environ.get("BRIDGE_CLAUDE_MODEL", "claude-opus-5")
CLAUDE_EFFORT = os.environ.get("BRIDGE_CLAUDE_EFFORT", "high")
# Per call. Opus at high effort spends minutes on the long file-generation prompts.
CALL_TIMEOUT = int(os.environ.get("BRIDGE_TIMEOUT", "900"))
JSON_RETRIES = 2
# An empty directory outside any git repo, so the CLI finds no project to load.
CWD = os.environ.get("BRIDGE_CWD", os.path.join(PKG, "results", "runs", "_bridge_cwd"))
LOG = os.environ.get("BRIDGE_LOG", os.path.join(PKG, "results", "runs", "claude_bridge.log"))

os.makedirs(CWD, exist_ok=True)
os.makedirs(os.path.dirname(LOG), exist_ok=True)

# Counters for the health endpoint, so a long run can be watched without reading the log.
STATS = {"calls": 0, "failed": 0, "usage_limit": 0, "json_retries": 0, "seconds": 0.0,
         "prompt_tokens": 0, "completion_tokens": 0, "thinking_tokens": 0,
         "started": time.time()}


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def child_env():
    env = dict(os.environ)
    # Subscription only: never let a key turn this into metered API usage.
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        env.pop(k, None)
    # A parent Claude Code session exports these; inherited, they confuse the child.
    for k in list(env):
        if k.startswith("CLAUDE_CODE_") or k in ("CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT"):
            env.pop(k, None)
    # No title/summary side-calls to a small model on every invocation.
    env["DISABLE_NON_ESSENTIAL_MODEL_CALLS"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


class UsageLimit(RuntimeError):
    """The subscription window is exhausted. Carries the epoch it resets at, which the
    benchmark driver waits for instead of recording the case as a failure."""

    def __init__(self, resets_at, detail=""):
        self.resets_at = resets_at
        super().__init__(f'usage_limit_reached; "resets_at": {resets_at}; {detail[:300]}')


LIMIT_MARKERS = ("usage limit reached", "usage_limit", "rate limit exceeded",
                 "exceeded your account's", "upgrade to increase")


def parse_resets_at(text):
    """Best effort epoch of the next window. Claude reports the reset in several shapes;
    when none is found, assume an hour, which is what the driver then waits."""
    for pat in (r'"resets?_?[aA]t"\s*:\s*"?(\d{10,13})', r'reached\|(\d{10,13})'):
        m = re.search(pat, text)
        if m:
            v = int(m.group(1))
            return v // 1000 if v > 10 ** 11 else v
    return int(time.time()) + 3600


def run_claude(user_prompt, system_prompt, model):
    """One stateless `claude -p`. The CLI is stripped down to a text completion:
    --tools "" removes every built-in tool, --safe-mode keeps CLAUDE.md, skills, hooks
    and plugins out of the prompt, and sessions are not persisted (a full benchmark is
    a few thousand calls). The prompt goes in on stdin, not argv."""
    sys_p = (system_prompt or "You are a helpful assistant.") + \
        "\n\nIMPORTANT: You are running headless as a pure text-completion backend. " \
        "Answer directly with the requested content only. Do NOT use any tools. " \
        "Do NOT add meta commentary."
    cmd = [CLAUDE_BIN, "-p",
           "--model", model,
           "--effort", CLAUDE_EFFORT,
           "--output-format", "json",
           "--system-prompt", sys_p,
           "--tools", "",
           "--safe-mode",
           "--strict-mcp-config",
           "--disable-slash-commands",
           "--no-session-persistence"]
    p = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True,
                       timeout=CALL_TIMEOUT, cwd=CWD, env=child_env())
    raw = (p.stdout or "") + "\n" + (p.stderr or "")
    if any(m in raw.lower() for m in LIMIT_MARKERS):
        raise UsageLimit(parse_resets_at(raw), raw)
    if p.returncode != 0:
        # The CLI reports errors on stdout, not stderr; both are quoted so a failure is
        # diagnosable from the workflow log alone.
        raise RuntimeError(f"claude -p rc={p.returncode}: "
                           f"stdout={(p.stdout or '').strip()[:400]!r} "
                           f"stderr={(p.stderr or '').strip()[:400]!r}")
    try:
        data = json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception as e:
        raise RuntimeError(f"claude -p returned unparseable JSON ({e}): "
                           f"{(p.stdout or '')[:400]!r}")
    if data.get("is_error"):
        detail = json.dumps(data)[:600]
        if any(m in detail.lower() for m in LIMIT_MARKERS):
            raise UsageLimit(parse_resets_at(detail), detail)
        raise RuntimeError(f"claude -p reported an error: {detail}")
    usage = data.get("usage") or {}
    # thinking_tokens is the audit trail for --effort: it is the only place the CLI
    # reports how much reasoning the level actually bought. Measured on one prompt,
    # low gave 90 and high 1198, so the flag is not cosmetic.
    return (data.get("result") or "").strip(), {
        "prompt_tokens": int(usage.get("input_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
        + int(usage.get("cache_read_input_tokens") or 0),
        "completion_tokens": int(usage.get("output_tokens") or 0),
        "thinking_tokens": int((usage.get("output_tokens_details") or {}).get(
            "thinking_tokens") or 0),
    }


def extract_json(text):
    """Strip fences, take the outermost {...}; raise if it is not valid JSON."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    if not t.startswith("{"):
        s, e = t.find("{"), t.rfind("}")
        if s == -1 or e <= s:
            raise ValueError("no JSON object found")
        t = t[s:e + 1]
    json.loads(t)
    return t


def flatten(messages):
    """OpenAI messages -> (system, user). Every call carries its whole context already;
    Foam-Agent never sends a multi-turn conversation."""
    sys_parts, user_parts = [], []
    for m in messages:
        role, content = m.get("role"), m.get("content") or ""
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        (sys_parts if role == "system" else user_parts).append(
            content if role in ("system", "user") else f"[{role}]: {content}")
    return "\n\n".join(sys_parts), "\n\n".join(user_parts)


def structured_spec(body):
    """(schema, name, kind) for a structured request, else (None, None, None).
    kind 'tool' -> answer as tool_calls; 'json' -> answer as JSON content."""
    tools = body.get("tools") or []
    if tools:
        fn = tools[0].get("function", {})
        return fn.get("parameters") or {}, fn.get("name", "output"), "tool"
    rf = body.get("response_format") or {}
    if rf.get("type") == "json_schema":
        js = rf.get("json_schema") or {}
        return js.get("schema") or {}, js.get("name", "output"), "json"
    if rf.get("type") == "json_object":
        return {}, "output", "json"
    return None, None, None


def account(usage, seconds):
    STATS["calls"] += 1
    STATS["seconds"] += seconds
    for k in ("prompt_tokens", "completion_tokens", "thinking_tokens"):
        STATS[k] += int((usage or {}).get(k) or 0)


def openai_response(model, content=None, tool_call=None, usage=None):
    msg = {"role": "assistant", "content": content}
    finish = "stop"
    if tool_call is not None:
        msg["content"] = None
        msg["tool_calls"] = [{"id": f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                              "function": tool_call}]
        finish = "tool_calls"
    u = {k: int((usage or {}).get(k) or 0) for k in ("prompt_tokens", "completion_tokens")}
    u["total_tokens"] = u["prompt_tokens"] + u["completion_tokens"]
    return {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": u}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        up = int(time.time() - STATS["started"])
        self._send(200, {"status": "claude-bridge ok", "model": CLAUDE_MODEL,
                         "effort": CLAUDE_EFFORT, "uptime_s": up, **STATS})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._send(404, {"error": {"message": f"unknown path {self.path}"}})
        t0 = time.time()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            system_p, user_p = flatten(body.get("messages", []))
            schema, fn_name, kind = structured_spec(body)
            model = body.get("model", CLAUDE_MODEL)

            if kind is None:
                out, usage = run_claude(user_p, system_p, CLAUDE_MODEL)
                account(usage, time.time() - t0)
                log(f"OK text  dur={time.time()-t0:.1f}s in={len(system_p)+len(user_p)}B "
                    f"out={len(out)}B tok={usage['prompt_tokens']}/{usage['completion_tokens']} "
                    f"think={usage['thinking_tokens']}")
                return self._send(200, openai_response(model, content=out, usage=usage))

            ask = user_p + ("\n\nRespond with ONLY a valid JSON object (no markdown, "
                            "no explanations) that conforms exactly to this JSON Schema:\n"
                            + json.dumps(schema))
            last_err = None
            for attempt in range(1 + JSON_RETRIES):
                out, usage = run_claude(ask, system_p, CLAUDE_MODEL)
                try:
                    j = extract_json(out)
                    break
                except Exception as e:
                    last_err = e
                    STATS["json_retries"] += 1
                    log(f"retry structured ({attempt+1}): bad JSON ({e}); head={out[:120]!r}")
            else:
                raise RuntimeError(f"structured output never parsed: {last_err}")
            account(usage, time.time() - t0)
            log(f"OK {kind}  fn={fn_name} dur={time.time()-t0:.1f}s in={len(ask)}B "
                f"out={len(j)}B tries={attempt+1} tok={usage['prompt_tokens']}/"
                f"{usage['completion_tokens']} think={usage['thinking_tokens']}")
            if kind == "tool":
                return self._send(200, openai_response(
                    model, tool_call={"name": fn_name, "arguments": j}, usage=usage))
            return self._send(200, openai_response(model, content=j, usage=usage))

        except UsageLimit as e:
            STATS["usage_limit"] += 1
            log(f"LIMIT {e}")
            # 429 with the marker text the driver greps for in workflow.log.
            self._send(429, {"error": {"message": str(e), "type": "rate_limit_error",
                                       "code": "usage_limit_reached",
                                       "resets_at": e.resets_at}})
        except subprocess.TimeoutExpired:
            STATS["failed"] += 1
            log(f"FAIL timeout after {CALL_TIMEOUT}s")
            self._send(500, {"error": {"message": f"claude call timed out after "
                                                  f"{CALL_TIMEOUT}s", "type": "server_error"}})
        except Exception as e:
            STATS["failed"] += 1
            log(f"FAIL dur={time.time()-t0:.1f}s err={str(e)[:300]}")
            self._send(500, {"error": {"message": str(e)[:800], "type": "server_error"}})


if __name__ == "__main__":
    rc = subprocess.run([CLAUDE_BIN, "--version"], capture_output=True, text=True)
    if rc.returncode != 0:
        sys.exit(f"`{CLAUDE_BIN} --version` failed; is the Claude Code CLI installed?")
    log(f"claude-bridge on {HOST}:{PORT}  model={CLAUDE_MODEL} effort={CLAUDE_EFFORT} "
        f"cli={rc.stdout.strip()} timeout={CALL_TIMEOUT}s cwd={CWD}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
