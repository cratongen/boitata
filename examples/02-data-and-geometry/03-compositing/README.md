# Compositing

The stacked sulfide lenses: 19 340 assays, mostly 1 m or 2 m, taken only in and around the mineralized zones, and 2240
lithology intervals. Compositing brings the assays to one support. It must not average across a contact, read
unsampled core as zero, or create or lose metal.

<details><summary>Python</summary>

```python
import boitata as bt
import matplotlib.pyplot as plt
import numpy as np
from common import ACCENT, GRAY, LIGHT, save
```

</details>

Assays and lithology come in separate interval tables. `merge_intervals` splits both at each boundary so each piece
carries its grades and its lithology. Pieces outside the assayed zones have no grades.

<details><summary>Python</summary>

```python
data = bt.datasets.stacked_sulphide_lenses()
collar, survey, assay, lithology = data["collars"], data["surveys"], data["assays"], data["lithology"]
GRADES = ["ZN_PCT", "PB_PCT", "CU_PCT", "AG_GPT", "AU_GPT"]
intervals = bt.merge_intervals(assay, lithology)
dh = bt.Drillholes(collar, survey, intervals)
print(f"{assay.num_rows} assays + {lithology.num_rows} lithology intervals -> {intervals.num_rows} merged")
print(dh)
```

</details>

```text
19340 assays + 2240 lithology intervals -> 20215 merged
Drillholes  289 holes, 20,215 intervals
  bounds  x 11748.8 to 12953.9, y 29207.3 to 30526.2, z -275.7 to 397.4
  interval columns
  column   type     unit   nulls    min    mean    max
  HOLE_ID  str                 0  289 unique: DD0001, DD0002, DD0003, …
  FROM     float64             0      0   299.8  876.7
  TO       float64             0   2.25   305.9  878.6
  ZN_PCT   float64           875  0.003  0.6725  40.77
  PB_PCT   float64           875  0.001  0.2691  25.75
  CU_PCT   float64           875      0  0.1392   16.5
  AG_GPT   float64           875      0   6.727    594
  AU_GPT   float64         6,236      0  0.1682  17.71
  DENSITY  float64        18,998   2.82   3.293    4.8
  LITH     str                 0  8 unique: OB, VCL, FWV, …
```

Compositing to 2 m by `LITH` cuts intervals at each 2 m mark and at each contact, so no composite averages across
one. A grade is the mean over the length that carries a value, which keeps unsampled core from counting as zero.
Each grade returns that length as `<grade>_length`, next to `length`, which also counts unsampled ground.
Composites without assays are dropped. Here the assayed zones start and end at lithology contacts, so inside a
lithology Zn is sampled everywhere. The RC holes have no Au assays.

<details><summary>Python</summary>

```python
composites = dh.composite(2.0, GRADES, domain="LITH")
partial = composites["ZN_PCT_length"] < composites["length"] - 1e-9
no_au = np.isnan(composites["AU_GPT"])
print(
    f"{len(composites)} composites; {partial.sum()} partly unsampled for Zn; {no_au.sum()} without Au (RC holes)"
)
```

</details>

```text
16811 composites; 229 partly unsampled for Zn; 2754 without Au (RC holes)
```

The assays are mostly 1 m or 2 m and the composites 2 m, with shorter tails where a run of one lithology ends.

<details><summary>Python</summary>

```python
raw_len = assay["TO"] - assay["FROM"]
fig, ax = plt.subplots(figsize=(6, 3.4), layout="constrained")
bins = np.arange(0, 3.0, 0.125)
ax.hist(raw_len, bins, color=LIGHT, edgecolor=GRAY, lw=0.5, label="Assays")
ax.hist(composites["length"], bins, histtype="step", color=ACCENT, lw=1.6, label="Composites")
ax.set(title="Interval lengths", xlabel="Length (m)", ylabel="Count")
ax.legend(loc="upper left")
save(fig, "compositing")
```

</details>

![compositing](compositing.png)

Other supports. `length=None` gives one composite per run of a lithology. `intervals=` composites to given
intervals instead, here 10 m benches: the depths where each desurveyed path crosses a bench elevation. `residual=`
decides what happens to a run's tail shorter than `min_fraction` of the length: kept, merged into the previous
composite or dropped. Without `domain`, composites cross contacts and `categories=` gives the lithology covering
most of each.

<details><summary>Python</summary>

```python
BENCH = 10.0
paths = dh.paths()
hole, depth, z = paths["HOLE_ID"], paths["depth"], paths["z"]
cuts = {h: [0.0, depth[hole == h].max()] for h in np.unique(hole)}
for i in np.flatnonzero(hole[1:] == hole[:-1]):
    lo, hi = sorted((z[i], z[i + 1]))
    for level in np.arange(np.ceil(lo / BENCH) * BENCH, hi, BENCH):
        cuts[hole[i]].append(depth[i] + (level - z[i]) / (z[i + 1] - z[i]) * (depth[i + 1] - depth[i]))
benches = {"HOLE_ID": [], "FROM": [], "TO": []}
for h, c in cuts.items():
    c = np.unique(c)
    benches["HOLE_ID"] += [h] * (len(c) - 1)
    benches["FROM"] += list(c[:-1])
    benches["TO"] += list(c[1:])

modes = {
    "2 m": composites,
    "runs": dh.composite(None, GRADES, domain="LITH"),
    "10 m benches": dh.composite(None, GRADES, domain="LITH", intervals=benches),
    "2 m, merge < 1 m": dh.composite(2.0, GRADES, domain="LITH", residual="merge"),
    "2 m, drop < 1 m": dh.composite(2.0, GRADES, domain="LITH", residual="drop"),
    "2 m, majority LITH": dh.composite(2.0, GRADES, categories=["LITH"]),
}
for name, c in modes.items():
    print(f"{name:>18}: {len(c):6} composites, median length {np.median(c['length']):.1f} m")
```

</details>

```text
               2 m:  16811 composites, median length 2.0 m
              runs:   1602 composites, median length 9.2 m
      10 m benches:   4213 composites, median length 9.4 m
  2 m, merge < 1 m:  16220 composites, median length 2.0 m
   2 m, drop < 1 m:  16125 composites, median length 2.0 m
2 m, majority LITH:  16031 composites, median length 2.0 m
```

Metal balance: Σ grade × `<grade>_length` over the composites reproduces Σ grade × interval length over the assays,
for each grade and each mode except `drop`, which leaves its short tails out. Weighting by `length` instead
counts unsampled ground at the composite grade and inflates metal, here where majority-`LITH` composites cross a
contact into unassayed rock.

<details><summary>Python</summary>

```python
def metal(grade, length):
    return np.nansum(grade * length)


assayed = {g: metal(assay[g], raw_len) for g in GRADES}
print(f"{'':>18}  {'Zn metal':>10}  {'error':>8}  {'by length':>9}")
print(f"{'assays':>18}  {assayed['ZN_PCT']:10.1f}")
for name, c in modes.items():
    zn_metal = metal(c["ZN_PCT"], c["ZN_PCT_length"])
    error, naive = zn_metal / assayed["ZN_PCT"] - 1, metal(c["ZN_PCT"], c["length"]) / assayed["ZN_PCT"] - 1
    print(f"{name:>18}  {zn_metal:10.1f}  {error:+8.1e}  {naive:+9.1%}")
    if name != "2 m, drop < 1 m":
        for g in GRADES:
            assert abs(metal(c[g], c[f"{g}_length"]) / assayed[g] - 1) < 1e-9, (name, g)
print("metal balanced to 1e-9 for", ", ".join(GRADES))
```

</details>

```text
                      Zn metal     error  by length
            assays     20514.3
               2 m     20514.3  +0.0e+00      +0.1%
              runs     20514.3  +0.0e+00      +6.9%
      10 m benches     20514.3  +0.0e+00      +0.3%
  2 m, merge < 1 m     20514.3  +0.0e+00      +0.1%
   2 m, drop < 1 m     19797.3  -3.5e-02      -3.4%
2 m, majority LITH     20514.3  +0.0e+00      +0.1%
metal balanced to 1e-9 for ZN_PCT, PB_PCT, CU_PCT, AG_GPT, AU_GPT
```

Full script: [`example_02_03.py`](example_02_03.py)
