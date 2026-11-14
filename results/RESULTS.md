## 2026-11-14 (evening): priority lanes, Flash-Next IQ3_S on one B60, Windows

Engine: Strata b60-windows HEAD 8f72c4df + the patch in `patches/` (now commit bc40c907). Config: `config/`
(`--batch 2 --batch-mtp`, `--prefill 4096`, `STRATA_SPIN_MAX=200000000`). Request field: `"priority": N` (or `"high"` = 1).
Bench scripts: `bench/fnbench.py`, `bench/calltest.py`.

Short prompts, machine mostly quiet:

| case | high stream | other stream |
|---|---|---|
| one stream | 38-42 tok/s | |
| two equal | 19-21 | 18-21 |
| priority gap 1 | 29 | 8 |
| priority gap 4 | 35 | 2 |
| gap 4, 95K context on each | 23.5 | 1.5 |

Call (priority 4, 8 short turns) while a chat request reads a 95K prompt, two runs, 16/16 replies clean:
first token 2.2-4.2 s, decode 20-29 tok/s; the chat's first token after 125-131 s, then 25-33 tok/s.
Call beside a chat that is already generating: first token 0.8-1.8 s.

Prompt chunk vs call wait during a 95K read: 32K chunks 1,500 tok/s read / 17-25 s first token; 8K 1,150 / 5-8.5 s;
4K 935 / 2.2-4.2 s; 2K 725 / 1.6-4.4 s.

What changed in the engine:
- batch windows run the adaptive expert tier (it only ran in the solo loop, so the VRAM tier stayed as the last solo
  request left it: 46-54% hits for a slot on other text, 17-19 tok/s). Not while a prompt's loan is out, and its swaps
  land before a read lends slots (both were bugs in the first version: a crash, then corrupted replies).
- a batched read below a decoding slot's priority waits for that reply before it lends slots and before each chunk;
  the server sends BYIELD for a waiting request of higher priority, whatever its length.
- STRATA_SPIN_MAX 2,000,000 was not enough when the engine is starved of CPU (engine pinned to 2 logical cores:
  1 corrupted reply in 4). With 200,000,000: 0 in 8, same speed unstarved. Small sample.

Not measured on a quiet machine: other jobs (embedding servers, an image render) and a
priority script (lowers strata to BelowNormal) were active during most runs; the load before each run is in the logs.

### Final config (same evening): lanes + refusal vector, `strata-iq3_s-b60-lanes-esp.json`, patch in `patches/`

Added after the table above: `STRATA_LANE_WAIT_MS` (default 4000, one allowance per request) so a lower request is not
held for a whole long reply; control vector on by default.

- one stream 37-45 tok/s; gap 4: high 29-36, other about 2 during, 31-33 after (3 runs); a lower request arriving
  during a long higher reply: first token 7.8-8.6 s.
- call during a 95K chat read: first token 2.4-3.2 s, 19-29 tok/s, 8/8 clean.
- quality probe (16 reasoning questions, 6 tool calls, 16 refusal prompts), vector on: reasoning 16/16 (think off) and 16/16 (think on), tools 6/6, refused 0/16.
  Vector off per request on the same server: 16/16, 16/16, 6/6, refused 11/16.
- opencode coding tasks, vector on: 5/5 (bugfix, cache, cli, rootcause, data; 94-209 s each).
  The 2026-11-13 run without the vector was 3/5 (cache and cli failed). Single runs.
- started through the launcher on :8080 (engine at BelowNormal): 39-42 tok/s alone, gap 4 high 31, sanity ok.
  RAM 59.3 GB working set, 82.1 GB private, card 22.7 GiB.

### 2026-11-14 night: re-measure with the three-tier priorities in place

Engine at BelowNormal, other jobs at Idle (one of them using about 7 cores), CPU load 30-49% before the runs.
- one stream 36.0-37.7 tok/s; two equal 16.4/15.0 and 20.3/25.1; gap 4: high 35.6, other 2.4 during and 27.0 overall.
- two streams with 200K-token prompts each (199,555 tokens), equal priority: read 789 tok/s; the first stream decoded at
  2.9 tok/s while the second read its prompt; with both contexts cached they decode together at 9.1 and 11.4 tok/s.
  0/2 degenerate. Peak working set 81.7 GB during the reads, 58.2 GB after; private 84.2 GB.
