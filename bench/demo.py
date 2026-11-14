"""Terminal demo against a local OpenAI-compatible server: live streaming with measured speeds.

usage: demo.py BASE_URL
Scene 1: one stream. Scene 2: two equal streams. Scene 3: a priority-4 stream beside a normal one.
The live figure is streamed pieces per second (a piece is one token or more, so it is a floor); the line
printed when a stream ends is completion_tokens and wall time from the server's usage block.
"""
import json, os, shutil, sys, textwrap, threading, time, urllib.request

BASE = sys.argv[1]
os.system("")  # turns on ANSI escapes in the Windows console
W, H = shutil.get_terminal_size((120, 34))
W -= 1   # a line as wide as the window wraps
TITLE = "Qwen3.8-Flash-Next (IQ3_S)  |  one Intel Arc Pro B60 24 GB  |  Windows 11  |  Strata engine  |  real time, unedited"


class Stream:
    def __init__(self, name, prompt, max_tokens, priority=0):
        self.name, self.prompt, self.max_tokens, self.priority = name, prompt, max_tokens, priority
        self.text, self.pieces, self.t0, self.first, self.last, self.ct, self.done = "", 0, None, None, None, 0, False

    def run(self):
        body = {"model": "x", "stream": True, "max_tokens": self.max_tokens, "temperature": 0, "stream_options": {"include_usage": True},
                "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False},
                "messages": [{"role": "user", "content": self.prompt}]}
        if self.priority:
            body["priority"] = self.priority
        req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        self.t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=3600) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                j = json.loads(line[5:])
                for ch in j.get("choices") or []:
                    piece = (ch.get("delta") or {}).get("content") or ""
                    if piece:
                        now = time.perf_counter(); self.first = self.first or now; self.last = now
                        self.text += piece; self.pieces += 1
                u = j.get("usage") or {}
                if u.get("completion_tokens"):
                    self.ct = u["completion_tokens"]
        self.done = True

    def status(self):
        if not self.first:
            return "reading the prompt ..."
        if self.done and self.ct and self.last > self.first:
            return f"DONE  {self.ct} tokens in {self.last - self.first:.1f} s  =  {(self.ct - 1) / (self.last - self.first):.1f} tok/s"
        el = max(time.perf_counter() - self.first, 1e-6)
        # streamed pieces per second: a piece is one token or more, so this is a floor; the DONE line is the server's count
        return f"streaming  {self.pieces / el:.0f}+ tok/s"


def pane(s, width, height):
    lines = []
    for para in s.text.split("\n"):
        lines += textwrap.wrap(para, width) or [""]
    lines = lines[-height:]
    return [ln.ljust(width)[:width] for ln in lines] + [" " * width] * (height - len(lines))


def show(scene, streams, hold=3.0):
    ths = [threading.Thread(target=s.run, daemon=True) for s in streams]
    for t in ths:
        t.start()
        time.sleep(0.05)
    n = len(streams)
    pw = (W - 3 * (n - 1) - 2) // n
    ph = H - 9
    end = None
    while True:
        out = ["\x1b[H\x1b[1;36m" + TITLE[:W].ljust(W) + "\x1b[0m", "\x1b[1m" + scene[:W].ljust(W) + "\x1b[0m", "-" * W]
        heads = [("\x1b[1;33m" if s.priority else "\x1b[1;32m") + f"{s.name}".ljust(pw)[:pw] + "\x1b[0m" for s in streams]
        out.append(" | ".join(heads))
        panes = [pane(s, pw, ph) for s in streams]
        for i in range(ph):
            out.append(" | ".join(p[i] for p in panes))
        out.append("-" * W)
        out.append(" | ".join("\x1b[1;37m" + s.status().ljust(pw)[:pw] + "\x1b[0m" for s in streams))
        sys.stdout.write("\n".join(out) + "\x1b[J"); sys.stdout.flush()
        if all(s.done for s in streams):
            end = end or time.perf_counter()
            if time.perf_counter() - end > hold:
                break
        time.sleep(0.07)


P_BIKE = "Explain in detail how a bicycle stays upright while moving. Cover steering geometry, gyroscopic effects and rider input."
P_CODE = "Write a complete Python module implementing an LRU cache with TTL support, with type hints, docstrings and a small usage example."
P_CALL = ("You are a phone support agent for a small online shop. A customer says their order is nine days late and the tracking page "
          "has not changed since Monday. Explain what you will do, the refund process and how long it takes, in a calm spoken style.")

sys.stdout.write("\x1b[2J")
show("1 / 3   one stream", [Stream("stream A", P_BIKE, 350)])
show("2 / 3   two streams, equal priority", [Stream("stream A", P_BIKE, 280), Stream("stream B", P_CODE, 280)])
show("3 / 3   priority lanes: the call is sent with \"priority\": 4, the chat keeps going and speeds up when the call ends",
     [Stream("CALL  (priority 4)", P_CALL, 300, 4), Stream("CHAT  (priority 0)", P_CODE, 900)], hold=4.0)
