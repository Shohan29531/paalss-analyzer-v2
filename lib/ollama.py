import json
from typing import Dict, Generator, List, Optional

import requests


class OllamaError(RuntimeError):
    pass


# ---------- Helpers ----------

def _headers(api_key: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _strip_trailing_slash(s: str) -> str:
    return (s or "").strip().rstrip("/")


def _mk_url(host: str, path: str) -> str:
    host = _strip_trailing_slash(host)
    if not path.startswith("/"):
        path = "/" + path
    return host + path


def _raise_http(r: requests.Response, url: str, prefix: str) -> None:
    """Raise a rich error including response body (helps debug 404 model-not-found vs path-not-found)."""
    try:
        body = r.text
    except Exception:
        body = ""
    body_snip = (body[:800] + "…") if body and len(body) > 800 else body
    raise OllamaError(f"{prefix} at {url}: {r.status_code} {r.reason}\n{body_snip}".strip())


def _looks_like_path_not_found(resp_text: str) -> bool:
    t = (resp_text or "").lower()
    # Common Ollama error shape: {"error":"path \"/api/...\" not found"}
    return ("path" in t and "not found" in t) or ("no route" in t)


# ---------- Model listing ----------

def list_models(host: str, api_key: Optional[str] = None, timeout_s: int = 20) -> List[str]:
    """
    Return a list of model names available on the target Ollama host.

    Tries native Ollama API first (/api/tags). If that 404s, falls back to
    OpenAI-compatible listing (/v1/models).
    """
    host = _strip_trailing_slash(host)

    # Native: /api/tags
    url = _mk_url(host, "/api/tags")
    try:
        r = requests.get(url, headers=_headers(api_key), timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        if r.status_code != 404:
            _raise_http(r, url, "Failed to list models")
    except requests.RequestException as e:
        raise OllamaError(f"Failed to list models from {url}: {e}")

    # Fallback: OpenAI compat /v1/models
    url2 = _mk_url(host, "/v1/models")
    try:
        r2 = requests.get(url2, headers=_headers(api_key), timeout=timeout_s)
        if r2.status_code != 200:
            _raise_http(r2, url2, "Failed to list models")
        data = r2.json()
        items = data.get("data") or []
        # OpenAI format: [{"id": "modelname", ...}, ...]
        out = []
        for it in items:
            mid = it.get("id") or it.get("name")
            if mid:
                out.append(str(mid))
        return out
    except requests.RequestException as e:
        raise OllamaError(f"Failed to list models from {url2}: {e}")


# ---------- Chat (native + OpenAI fallback) ----------

def chat_once(
    host: str,
    api_key: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    timeout_s: int = 120,
) -> str:
    """
    Non-streaming chat call.

    Uses native Ollama endpoint POST /api/chat.
    If it returns 404 (often happens when a provider expects OpenAI-compat paths),
    automatically falls back to POST /v1/chat/completions.
    """
    host = _strip_trailing_slash(host)

    # Native
    url = _mk_url(host, "/api/chat")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
        r = requests.post(url, headers=_headers(api_key), json=payload, timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            return (data.get("message") or {}).get("content", "")
        if r.status_code != 404:
            _raise_http(r, url, "Chat failed")
        # If 404, fall back to OpenAI compat
        resp_text = ""
        try:
            resp_text = r.text
        except Exception:
            pass
    except requests.RequestException as e:
        raise OllamaError(f"Chat failed at {url}: {e}")

    # OpenAI compat fallback
    url2 = _mk_url(host, "/v1/chat/completions")
    payload2 = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    try:
        r2 = requests.post(url2, headers=_headers(api_key), json=payload2, timeout=timeout_s)
        if r2.status_code != 200:
            # If native 404 was model-not-found, surface that too (it’s the most actionable).
            if resp_text and not _looks_like_path_not_found(resp_text):
                raise OllamaError(f"Chat failed at {url}: {r.status_code} {r.reason}\n{resp_text[:800]}")
            _raise_http(r2, url2, "Chat failed")
        data2 = r2.json()
        # OpenAI format: choices[0].message.content
        choices = data2.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return msg.get("content", "") or ""
    except requests.RequestException as e:
        raise OllamaError(f"Chat failed at {url2}: {e}")


def chat_stream(
    host: str,
    api_key: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    timeout_s: int = 120,
) -> Generator[str, None, None]:
    """
    Streaming chat call (yields incremental text chunks).

    Uses native Ollama endpoint POST /api/chat with stream=true.
    If it returns 404, automatically falls back to OpenAI-compatible streaming
    at POST /v1/chat/completions (SSE: 'data: {...}' lines).
    """
    host = _strip_trailing_slash(host)

    # Native streaming
    url = _mk_url(host, "/api/chat")
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }

    try:
        with requests.post(
            url,
            headers=_headers(api_key),
            json=payload,
            stream=True,
            timeout=timeout_s,
        ) as r:
            if r.status_code == 200:
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = data.get("message") or {}
                    chunk = msg.get("content")
                    if chunk:
                        yield chunk

                    if data.get("done"):
                        break
                return

            if r.status_code != 404:
                _raise_http(r, url, "Streaming chat failed")

            # Save body (may be empty for streaming) for better error attribution
            resp_text = ""
            try:
                resp_text = r.text
            except Exception:
                pass
    except requests.RequestException as e:
        raise OllamaError(f"Streaming chat failed at {url}: {e}")

    # OpenAI compat streaming fallback (SSE)
    url2 = _mk_url(host, "/v1/chat/completions")
    payload2 = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }

    try:
        with requests.post(
            url2,
            headers=_headers(api_key),
            json=payload2,
            stream=True,
            timeout=timeout_s,
        ) as r2:
            if r2.status_code != 200:
                if resp_text and not _looks_like_path_not_found(resp_text):
                    # Likely model-not-found from native; surface it.
                    raise OllamaError(f"Streaming chat failed at {url}: 404 Not Found\n{resp_text[:800]}")
                _raise_http(r2, url2, "Streaming chat failed")

            for raw in r2.iter_lines(decode_unicode=True):
                if not raw:
                    continue

                line = raw.strip()

                # SSE lines look like: "data: {...}"
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()

                if line == "[DONE]":
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # OpenAI streaming delta: choices[0].delta.content
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                chunk = delta.get("content")
                if chunk:
                    yield chunk
    except requests.RequestException as e:
        raise OllamaError(f"Streaming chat failed at {url2}: {e}")
