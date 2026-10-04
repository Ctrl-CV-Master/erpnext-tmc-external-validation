# -*- coding: utf-8 -*-
"""GLM API client with key pool, per-method model pinning, backoff and token accounting.

Protocol constraints (frozen):
  - temperature = 0 for every call
  - TMC-AE      -> glm-5.3-flashx (key pool GLM_API_KEY* with flashx quota)
  - R2/R3       -> glm-5.3-flash
  - If a pool runs dry, fall back to the other model for the SAME method and
    record the substitution in the run manifest.
Keys are read from environment variables only (GLM_API_KEY, GLM_API_KEY_2..N);
never logged, never written to trajectories.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def load_keys():
    keys = []
    i = 1
    while True:
        name = "GLM_API_KEY" if i == 1 else f"GLM_API_KEY_{i}"
        v = os.environ.get(name)
        if not v:
            if i > 12:
                break
            i += 1
            continue
        keys.append(v)
        i += 1
    return keys


class GLMClient:
    def __init__(self, model, tag="", max_tokens=1200):
        self.model = model
        self.fallback_model = "glm-5.3-flash" if "flashx" in model else "glm-5.3-flashx"
        self.keys = load_keys()
        if not self.keys:
            raise RuntimeError("no GLM API keys in environment (GLM_API_KEY*)")
        self.ki = 0
        self.tag = tag
        self.max_tokens = max_tokens
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.model_substitutions = []
        self._cooldown = {}

    def _next_key(self):
        for _ in range(len(self.keys)):
            k = self.keys[self.ki]
            self.ki = (self.ki + 1) % len(self.keys)
            cd = self._cooldown.get(k, 0)
            if cd < time.time():
                return k
        time.sleep(30)
        return self.keys[self.ki]

    def chat(self, messages, temperature=0.0, force_json=False):
        """Returns the assistant message text. Retries on 429/5xx/timeouts with
        exponential backoff; rotates keys. Counts tokens from usage."""
        body = {"model": self.model, "messages": messages,
                "temperature": temperature, "max_tokens": self.max_tokens}
        if force_json:
            body["response_format"] = {"type": "json_object"}
        delay = 5
        last_err = None
        for attempt in range(10):
            key = self._next_key()
            payload = json.dumps(body).encode()
            req = urllib.request.Request(
                ENDPOINT, data=payload, method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                usage = data.get("usage", {}) or {}
                self.input_tokens += usage.get("prompt_tokens", 0)
                self.output_tokens += usage.get("completion_tokens", 0)
                self.calls += 1
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                if e.code == 429:
                    self._cooldown[key] = time.time() + 60
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                if e.code in (401, 403):
                    # key invalid/exhausted -> drop from rotation
                    if key in self.keys:
                        self.keys.remove(key)
                        if not self.keys:
                            raise RuntimeError("all GLM keys exhausted/invalid")
                    continue
                if e.code == 400:
                    # possibly model not available for this key -> try fallback model once
                    if body["model"] != self.fallback_model:
                        self.model_substitutions.append(body["model"])
                        body["model"] = self.fallback_model
                        continue
                    raise
                if e.code >= 500:
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                raise
            except Exception as e:
                last_err = str(e)[:120]
                time.sleep(delay)
                delay = min(delay * 2, 120)
        raise RuntimeError(f"GLM chat failed after retries: {last_err}")

    def usage(self):
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "model": self.model, "substitutions": self.model_substitutions}
