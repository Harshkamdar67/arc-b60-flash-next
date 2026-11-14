**Title:** [Engine] Windows SYCL, one Arc Pro B60: "!!!!" replies are the 20,000-read spin bound expiring while the CPU computes experts

**Setup**

- Arc Pro B60 24 GB (driver 1.15.39183), Windows 11, i7-12700K, 128 GB DDR4-2667
- branch `b60-windows` of my fork (Windows SYCL port), Qwen3.8-Flash-Next GSQ-RCO IQ3_S, `--mtp`, `--spec 2`,
  `--kv int8 --kv-resident 32768`, `--max-context 262144`
- `STRATA_VERIFY_DEVICE_PLAN=1`, `STRATA_VERIFY_NO_HOST=0` (the card does not hold every expert, the CPU computes the rest)

**What happens**

About 1 reply in 10 is a run of `!` (token 0) from some point on. Speed looks normal or better than normal while it
happens, so a benchmark that does not read the text reports it as a good run.

**Cause**

`spin_max()` in `sycl/include/strata/sycl_doorbell.hpp` gives a B-series card without a sysfs driver name (Windows)
20,000 reads, the bound #1473 chose for xe device-plan windows whose waits are expected to expire. With
`STRATA_VERIFY_NO_HOST=0` the wait is not that kind: the card waits for the CPU's expert outputs at every layer, as the
comment above `spin_max()` describes for the A-series on i915. When the CPU is later than 20,000 reads, the kernel goes
on without those outputs and the window is wrong.

**Measurements** (text checked on every reply: a run of 8 or more `!`, or a nearly empty reply, counts as bad)

| STRATA_SPIN_MAX | machine | bad replies |
|---|---|---|
| default (20,000) | quiet | about 10% |
| 2,000,000 | quiet | 0 of about 110 |
| 2,000,000 | engine pinned to 2 logical cores | 1 of 4 |
| 200,000,000 | engine pinned to 2 logical cores | 0 of 8 |

Decode speed is the same with all three values when the machine is quiet (38-45 tok/s, one stream). The pinned test
is a way to make the CPU late on purpose; the same thing happened by itself when other programs took most of the cores
and the engine had been set to below-normal priority. No device reset or driver timeout was seen with the long bound on
Windows in these runs. The starved samples are small.

**Suggestion**

On Windows (no sysfs driver name), a B-series card running with `STRATA_VERIFY_NO_HOST=0` should get the long bound, the
way the A-series does, because its waits have to complete. I have not tested the xe driver on Linux and this does not
change it.

A longer bound still turns a late CPU into a wrong window if the wait does expire. Having the kernel record an expired
wait so the host can fail the request (or redo the window) would make this visible instead of silent. I have not written that.

**Reproduce**

1. Windows SYCL build, one B-series card, a model whose experts do not all fit in VRAM, `STRATA_VERIFY_NO_HOST=0`, `--mtp`.
2. Send 30 or more requests of 200-300 tokens and check each reply's text.
3. To make it frequent: set the engine process's affinity to two logical cores.
4. Repeat with `STRATA_SPIN_MAX=200000000`.
