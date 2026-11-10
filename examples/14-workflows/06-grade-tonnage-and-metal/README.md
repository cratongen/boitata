# Grade-tonnage curves and the change in contained metal

[Compare two estimates](../../14-workflows/05-compare-two-estimates/README.md) chose the ordinary kriging over the inverse distance
model of the metal survey. Management asks the next question: how much metal does that decision remove from the
resource? You build grade-tonnage curves for both models and for the true blocks, report tonnes, grade and metal
at a set of cutoffs, state the change in contained metal at the reporting cutoff, and check that the metal adds
up.

<details><summary>Python</summary>

```python
import boitata as bt
import matplotlib.pyplot as plt
import numpy as np
from common import ACCENT, HIGHLIGHT, INK, save
```

</details>

!!! learn "What you'll learn"
    - What a grade-tonnage curve reports: tonnes, mean grade and metal above each cutoff.
    - Why a smooth estimate reports more tonnes at a lower grade above a low cutoff.
    - How to state a change in contained metal in absolute and relative terms, and check that it balances.

    Prerequisites: [compare two estimates](../../14-workflows/05-compare-two-estimates/README.md), which builds the two models.
    [Result plots](../../10-checking-models/06-result-plots/README.md) documents `bt.plot.grade_tonnage`.

## The data

The blocks are those of the previous tutorial: 26 × 30 blocks of 10 × 10 m. A grade-tonnage report needs tonnes,
which the metal survey does not have, so two assumptions give them: a 10 m bench centered on the sample plane, and a
density of 2.7 t/m³. Each block is then 10 × 10 × 10 m = 1 000 m³ and weighs 2 700 t. The metal survey's `V` is read
as a grade in ppm (g/t), so tonnes × ppm gives grams of metal; the tables below divide by 10⁶ to report tonnes of
metal.

<details><summary>Python</summary>

```python
samples = bt.datasets.clustered_metal_survey()
xy, v = samples.coords, samples["V"]
azimuths = np.arange(0, 180, 22.5)
directional = [bt.experimental_variogram(xy, v, 10.0, 120.0, azimuth=a) for a in azimuths]
model = bt.Variogram.fit_directional(
    directional, [(a, 0) for a in azimuths], ["spherical", "spherical"], weighting="count/gamma"
)
search = bt.Search(radius=80, max_samples=24, min_samples=4, rotation=model.rotation, ratios=(0.5, 1.0))
kriging = bt.BlockKriging(model, search, size=(10, 10), discretization=(5, 5, 1)).fit(xy, v)
inverse = bt.InverseDistance(search, power=2).fit(xy, v)

density = 2.7
blocks = bt.BlockModel(origin=(0.5, 0.5, -5.0), size=(10, 10, 10), count=(26, 30, 1))
truth = bt.datasets.clustered_metal_survey_exhaustive()["V"].reshape(300, 260)
blocks = blocks.with_columns(
    {
        "ok": kriging.predict(blocks),
        "id": inverse.predict(blocks),
        "truth": truth.reshape(30, 10, 26, 10).mean(axis=(1, 3)).ravel(),
    }
)
tonnes = 10 * 10 * 10 * density
print(blocks)
print(f"{blocks['ok'].size} blocks × {tonnes:,.0f} t = {blocks['ok'].size * tonnes:,.0f} t")
```

</details>

```text
BlockModel  regular, 780 blocks
  count   26 × 30 × 1
  size    10 × 10 × 10
  origin  0.5, 0.5, -5
  bounds  x 0.5 to 260.5, y 0.5 to 300.5, z -5 to 5
  column  type     unit  nulls    min   mean     max
  ok      float64            0  5.594  287.4  1010.6
  id      float64            0  8.748  315.7  1002.1
  truth   float64            0  8.959  279.5  1077.2
780 blocks × 2,700 t = 2,106,000 t
```

The true blocks are the averages of the exhaustive grid over each block. A real deposit has no such column; here
it shows which model reports the right tonnes.

!!! step "Step 1: One grade-tonnage curve"
    For a cutoff \(c\), the tonnage is the sum of the tonnes of the blocks with grade ≥ \(c\), the mean grade is
    their tonne-weighted average, and the metal is tonnage × mean grade. `grade_tonnage` computes this for a list
    of cutoffs. `data=blocks` lets it read the column by name and use each block's volume as its weight;
    `density` turns volume into tonnes.

<details><summary>Python</summary>

```python
cutoffs = np.arange(0, 1001, 25.0)
curve = bt.grade_tonnage("ok", cutoffs, density=density, data=blocks)
print(curve.column_names)
for row in zip(*(curve[c] for c in ("cutoff", "tonnage", "mean_grade", "metal"))):
    if row[0] in (0, 200, 400):
        cutoff, t, g, m = row
        print(f"cutoff {cutoff:3.0f} ppm: {t / 1e6:.3f} Mt at {g:.1f} ppm = {m / 1e6:.1f} t of metal")
```

</details>

```text
['cutoff', 'tonnage', 'mean_grade', 'metal']
cutoff   0 ppm: 2.106 Mt at 287.4 ppm = 605.2 t of metal
cutoff 200 ppm: 1.391 Mt at 372.2 ppm = 517.6 t of metal
cutoff 400 ppm: 0.464 Mt at 552.4 ppm = 256.5 t of metal
```

??? math "The math"
    With block tonnes \(t_i\) and grades \(z_i\), for a cutoff \(c\):
    \[ T(c) = \sum_{z_i \ge c} t_i, \qquad M(c) = \sum_{z_i \ge c} t_i z_i, \qquad \bar z(c) = M(c) / T(c). \]
    At \(c = 0\) the metal is the whole model's, \(\sum_i t_i z_i\).

!!! step "Step 2: All three models on one set of cutoffs"
    `compare_models` repeats `grade_tonnage` for several columns of one block model (a dict names each one) and
    adds each model's difference from a `reference`. The true blocks are the reference here, to see which model
    is closer.

<details><summary>Python</summary>

```python
labels = {"truth": "True blocks", "ok": "Kriging", "id": "Inverse distance"}
columns = {label: name for name, label in labels.items()}
table = bt.compare_models(blocks, columns, cutoffs, reference="True blocks", density=density)


def at(table, name, cutoff):
    rows = (table["model"] == labels[name]) & (table["cutoff"] == cutoff)
    return {
        c: float(table[c][rows][0])
        for c in ("tonnage", "mean_grade", "metal", "tonnage_diff", "grade_diff", "metal_diff")
    }


print(
    f"{'cutoff':>6} {'model':>16} {'kt':>7} {'V ppm':>6} {'metal t':>8}   vs truth: {'t':>6} {'grade':>6} {'metal':>6}"
)
for cutoff in (0, 100, 200, 300, 400, 425, 600):
    for name, label in labels.items():
        r = at(table, name, cutoff)
        print(
            f"{cutoff:6.0f} {label:>16} {r['tonnage'] / 1e3:7.1f} {r['mean_grade']:6.1f} {r['metal'] / 1e6:8.1f}"
            f"             {r['tonnage_diff']:+6.1%} {r['grade_diff']:+6.1%} {r['metal_diff']:+6.1%}"
        )
```

</details>

```text
cutoff            model      kt  V ppm  metal t   vs truth:      t  grade  metal
     0      True blocks  2106.0  279.5    588.7              +0.0%  +0.0%  +0.0%
     0          Kriging  2106.0  287.4    605.2              +0.0%  +2.8%  +2.8%
     0 Inverse distance  2106.0  315.7    664.9              +0.0% +12.9% +12.9%
   100      True blocks  1601.1  351.7    563.2              +0.0%  +0.0%  +0.0%
   100          Kriging  1884.6  314.5    592.7             +17.7% -10.6%  +5.2%
   100 Inverse distance  1935.9  337.9    654.1             +20.9%  -3.9% +16.1%
   200      True blocks  1193.4  421.4    502.9              +0.0%  +0.0%  +0.0%
   200          Kriging  1390.5  372.2    517.6             +16.5% -11.7%  +2.9%
   200 Inverse distance  1501.2  389.6    584.9             +25.8%  -7.6% +16.3%
   300      True blocks   847.8  493.0    418.0              +0.0%  +0.0%  +0.0%
   300          Kriging   801.9  465.3    373.1              -5.4%  -5.6% -10.7%
   300 Inverse distance   953.1  469.4    447.4             +12.4%  -4.8%  +7.0%
   400      True blocks   531.9  581.7    309.4              +0.0%  +0.0%  +0.0%
   400          Kriging   464.4  552.4    256.5             -12.7%  -5.0% -17.1%
   400 Inverse distance   542.7  560.6    304.2              +2.0%  -3.6%  -1.7%
   425      True blocks   491.4  595.6    292.7              +0.0%  +0.0%  +0.0%
   425          Kriging   391.5  579.0    226.7             -20.3%  -2.8% -22.5%
   425 Inverse distance   472.5  582.3    275.1              -3.8%  -2.2%  -6.0%
   600      True blocks   218.7  723.9    158.3              +0.0%  +0.0%  +0.0%
   600          Kriging   143.1  714.4    102.2             -34.6%  -1.3% -35.4%
   600 Inverse distance   170.1  713.9    121.4             -22.2%  -1.4% -23.3%
```

Read the kriging rows against the truth. At 100 and 200 ppm kriging reports 17.7 % and 16.5 % too many tonnes at a
grade 10.6 % and 11.7 % too low; the metal is off by 5.2 % and 2.9 %, because the two errors partly cancel.
From 300 ppm up kriging reports too few tonnes (−5.4 % at 300, −34.6 % at 600). Figure 1 shows why.

<figure class="bt-figure">
--8<-- "svg/w2-smoothing-cutoff.svg"
<figcaption><b>Figure 1.</b> Two grade distributions with the same mean; the smoothed one is narrower (standard
deviation 0.6 of the true one). At a cutoff half a standard deviation below the mean, the smoothed estimate puts
80 % of the tonnes above cutoff against 69 % for the truth, and their mean grade drops from 0.51 to 0.21 standard
deviations above the mean. At cutoffs well above the mean, the narrow distribution loses tonnes as
well.</figcaption>
</figure>

!!! key "Key idea"
    Estimation averages neighboring samples, so estimated blocks vary less than true blocks. Above a low cutoff,
    a smooth model lifts waste blocks over the cutoff, adding tonnes and diluting the grade. Above a high cutoff, it pulls the rich blocks down under it and loses tonnes. Tonnage and grade move in
    opposite directions at low cutoffs, so the error in metal is smaller than the error in tonnes.

!!! step "Step 3: Draw the curves"
    `bt.plot.grade_tonnage` draws the `compare_models` table: tonnage solid on the left axis, mean grade
    dashed on the right, one color per model. Metal above cutoff is a third curve worth its own panel.

<details><summary>Python</summary>

```python
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
with plt.rc_context({"axes.prop_cycle": plt.cycler(color=[INK, ACCENT, HIGHLIGHT])}):
    bt.plot.grade_tonnage(table, ax=a)
a.set(xlabel="Cutoff V (ppm)", ylabel="Tonnage above cutoff (t)", title="Tonnage and grade above cutoff")
for name, color in (("truth", INK), ("ok", ACCENT), ("id", HIGHLIGHT)):
    rows = table["model"] == labels[name]
    b.plot(cutoffs, table["metal"][rows] / 1e6, color=color, label=labels[name])
b.axvline(200, color="gray", lw=0.8, ls="--")
b.set(xlabel="Cutoff V (ppm)", ylabel="Metal above cutoff (t)", title="Contained metal above cutoff")
b.legend()
save(fig, "grade_tonnage")
```

</details>

![grade_tonnage](grade_tonnage.png)

!!! step "Step 4: The change in contained metal at the reporting cutoff"
    The resource is reported above 200 ppm (the dashed line). Replacing the inverse distance model by the
    kriging changes the reported numbers as follows.

<details><summary>Python</summary>

```python
report = 200
old, new, true = (at(table, name, report) for name in ("id", "ok", "truth"))
for key, unit, scale in (("tonnage", "kt", 1e3), ("mean_grade", "ppm", 1), ("metal", "t", 1e6)):
    change = new[key] - old[key]
    print(
        f"{key:>10}: inverse distance {old[key] / scale:8.1f}, kriging {new[key] / scale:8.1f} {unit:>3}, "
        f"change {change / scale:+8.1f} {unit} ({change / old[key]:+.1%}); truth {true[key] / scale:8.1f}"
    )
```

</details>

```text
   tonnage: inverse distance   1501.2, kriging   1390.5  kt, change   -110.7 kt (-7.4%); truth   1193.4
mean_grade: inverse distance    389.6, kriging    372.2 ppm, change    -17.4 ppm (-4.5%); truth    421.4
     metal: inverse distance    584.9, kriging    517.6   t, change    -67.3 t (-11.5%); truth    502.9
```

Switching to kriging removes 110.7 kt (−7.4 %), 17.4 ppm of grade (−4.5 %) and 67.3 t of metal (−11.5 %).
Kriging's 517.6 t is still 2.9 % above the true 502.9 t; inverse distance was 16.3 % above it. At cutoff 0, where
no block is selected out, inverse distance holds 12.9 % more metal than the truth, against 2.8 % for
kriging: most of its excess is the clustering bias of the previous tutorial.

!!! pitfall "Pitfall: quoting only the tonnage change"
    "Kriging loses 7.4 % of the tonnes" is not the metal change, which is 11.5 % here. Tonnage alone can
    get the sign wrong: at 400 ppm inverse distance reports 2.0 % more tonnes than the truth but 1.7 % less metal.
    Report tonnes, grade and metal together, each in absolute and relative terms.

!!! check "Check before you move on"
    Metal must balance three ways: the reported metal equals tonnage × mean grade at every cutoff; at cutoff 0 it
    equals block tonnes × grade summed over all blocks; and above the reporting cutoff it equals the same sum over
    the blocks at or above the cutoff.

<details><summary>Python</summary>

```python
for name, label in labels.items():
    rows = table["model"] == label
    t, g, m = (table[c][rows] for c in ("tonnage", "mean_grade", "metal"))
    above = ~np.isnan(g)
    assert np.allclose(m[above], t[above] * g[above])
    grade = blocks[name]
    total = (tonnes * grade).sum()
    selected = (tonnes * grade[grade >= report]).sum()
    assert np.isclose(m[0], total) and np.isclose(at(table, name, report)["metal"], selected)
    print(
        f"{label:>16}: metal at cutoff 0 {m[0] / 1e6:5.1f} t = sum over blocks {total / 1e6:5.1f} t; "
        f"above {report} ppm {selected / 1e6:5.1f} t in {(grade >= report).sum()} blocks"
    )
```

</details>

```text
     True blocks: metal at cutoff 0 588.7 t = sum over blocks 588.7 t; above 200 ppm 502.9 t in 442 blocks
         Kriging: metal at cutoff 0 605.2 t = sum over blocks 605.2 t; above 200 ppm 517.6 t in 515 blocks
Inverse distance: metal at cutoff 0 664.9 t = sum over blocks 664.9 t; above 200 ppm 584.9 t in 556 blocks
```

All three models balance: for kriging, 605.2 t in the whole model, 517.6 t of it in the 515 blocks above
200 ppm. A metal figure that does not balance usually means blocks without a grade (null) were counted in the
tonnes, or the density was applied twice.

## The decision

Report the kriging: 1 390.5 kt at 372.2 ppm, 517.6 t of metal above 200 ppm. The change from the scoping
model is −67.3 t of metal (−11.5 %), which the clustering bias found in [compare two estimates](../../14-workflows/05-compare-two-estimates/README.md)
explains. The remaining smoothing (too many tonnes at too low a grade at this cutoff) is a change-of-support
problem: the [discrete Gaussian model](../../09-recoverable-resources/01-discrete-gaussian-model/README.md) and
[uniform conditioning](../../09-recoverable-resources/02-uniform-conditioning/README.md) estimate the tonnage a
selective mining unit would recover.

Full script: [`example_14_06.py`](example_14_06.py)
