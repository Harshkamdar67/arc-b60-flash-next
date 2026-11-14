"""A long low-priority request (chat with a big prompt) with short high-priority turns (a call) arriving during it.

usage: calltest.py BASE_URL CHAT_PROMPT_TOKENS [CALL_TURNS] [GAP_S] [PRIO]
The chat request starts first. After 8 s the first call turn is sent ("priority": PRIO, a growing conversation of short
turns, 120 tokens each); the next one GAP_S seconds after the previous reply ended. Prints, per call turn, the time to
its first token and its decode speed, and for the chat request its prompt reading time and decode speed.
"""
import json, random, sys, threading, time, urllib.request

BASE, PT = sys.argv[1], int(sys.argv[2])
TURNS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
GAP = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
PRIO = int(sys.argv[5]) if len(sys.argv) > 5 else 4
RUN = time.time_ns()
WORDS = ("the server reads a prompt and then writes tokens one at a time while the cache keeps earlier work so that a "
         "second request with the same start is quick but a new start must be read in full by the model on the card").split()


def stream(messages, max_tokens, prio):
    body = {"model": "x", "stream": True, "max_tokens": max_tokens, "temperature": 0, "stream_options": {"include_usage": True},
            "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}, "messages": messages}
    if prio:
        body["priority"] = prio
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); first = last = None; usage = {}; text = []
    with urllib.request.urlopen(req, timeout=7200) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            j = json.loads(line[5:])
            for ch in j.get("choices") or []:
                dl = ch.get("delta") or {}
                piece = (dl.get("content") or "") + (dl.get("reasoning_content") or "")
                if piece:
                    now = time.perf_counter(); first = first or now; last = now; text.append(piece)
            usage = j.get("usage") or usage
    ct = usage.get("completion_tokens", 0)
    return {"t0": t0, "first": first, "last": last, "pt": usage.get("prompt_tokens", 0), "ct": ct, "text": "".join(text),
            "decode": (ct - 1) / (last - first) if first and last and last > first else 0.0}


chat = {}


def chat_thread():
    rnd = random.Random(RUN)
    filler = " ".join(rnd.choice(WORDS) for _ in range(int(PT * 0.95)))
    msg = f"[chat-{RUN}] Notes follow.\n{filler}\n\nIgnore the notes. Write a complete Python module implementing an LRU cache with TTL support."
    chat.update(stream([{"role": "user", "content": msg}], 600, 0))


QUESTIONS = ["Hi, I'm calling about my order, it has not arrived yet. What should I do first?",
             "It was ordered nine days ago and the tracking page has not changed since Monday.",
             "Okay. Can you explain how a refund would work if it never shows up?",
             "And how long does the refund usually take to reach my bank?",
             "Thanks. One more thing, can I change the delivery address for future orders?",
             "Great, that's all. Summarise what we agreed in two sentences."]

T0 = time.perf_counter()
th = threading.Thread(target=chat_thread); th.start()
time.sleep(8)
msgs = [{"role": "system", "content": f"You are a phone support agent for a small online shop. Keep replies short and spoken. [call-{RUN}]"}]
for k in range(TURNS):
    msgs.append({"role": "user", "content": QUESTIONS[k % len(QUESTIONS)]})
    sent = time.perf_counter() - T0
    o = stream(msgs, 120, PRIO)
    msgs.append({"role": "assistant", "content": o["text"]})
    bad = "!!!!!!!!" in o["text"] or len(o["text"].strip()) < 10
    print(f"  call turn {k + 1} sent at {sent:5.1f} s: first token {o['first'] - o['t0']:.2f} s, decode {o['decode']:.1f} tok/s over {o['ct']} tok"
          f"{'  DEGENERATE' if bad else ''}", flush=True)
    time.sleep(GAP)
th.join()
print(f"  chat: prompt {chat['pt']} tok, first token after {chat['first'] - chat['t0']:.1f} s, decode {chat['decode']:.1f} tok/s over {chat['ct']} tok, "
      f"done at {chat['last'] - T0:.0f} s", flush=True)
