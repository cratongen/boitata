# Compare two estimates of one deposit

Two block models of the same deposit reach your desk: an ordinary kriging built by the resource geologist and an
inverse distance model built fast for a scoping study. They disagree, and you can report only one. You
compare them as a reviewer would, with the samples as the only evidence (global means, a difference map, block
against block, swaths, cross-validation), decide which to keep, and then check the decision against the true
grades, which the metal survey provides.

<details><summary>Python</summary>

```python
import boitata as bt
import matplotlib.pyplot as plt
import numpy as np
from common import ACCENT, GRAY, HIGHLIGHT, INK, map_axes, save
from matplotlib.colors import PowerNorm, TwoSlopeNorm
```

</details>

!!! learn "What you'll learn"
    - Why two estimates from the same samples can disagree by double-digit percentages.
    - Five checks that need only the samples: declustered mean, difference map, block-to-block scatter, swaths
      and cross-validation.
    - How to turn the checks into a decision you can defend.

    Prerequisites: [ordinary kriging](../../06-kriging/01-ordinary-kriging/README.md) and
    [simple estimators](../../06-kriging/02-simple-estimators/README.md). [Model checks](../../10-checking-models/01-model-checks/README.md)
    validates a single model; this page puts two side by side.

## The data

The 470 metal survey samples of `V` (ppm) are clustered: the later drilling concentrated on the high-grade areas.
Cell declustering gives each sample a weight that corrects for this, so the declustered mean is the best estimate
of the deposit mean the samples alone can give.

<details><summary>Python</summary>

```python
samples = bt.datasets.clustered_metal_survey()
xy, v = samples.coords, samples["V"]
weights = bt.cell_declustering(xy, v, sizes=np.arange(2.5, 102.5, 2.5)).weights
print(
    f"{len(v)} samples: naive mean {v.mean():.1f} ppm, "
    f"declustered mean {bt.describe(v, weights=weights)['mean']:.1f} ppm"
)
```

</details>

```text
470 samples: naive mean 406.7 ppm, declustered mean 281.6 ppm
```

!!! step "Step 1: Rebuild both estimates on the same blocks"
    Compare like with like, so that only the method differs: one block model of 10 × 10 m
    blocks, one search (up to 24 samples in an ellipse along the direction of greatest continuity), one set of
    samples. The kriging uses the variogram fitted in [ordinary kriging](../../06-kriging/01-ordinary-kriging/README.md)
    and estimates block averages; inverse distance weights each sample by 1/d².

<details><summary>Python</summary>

```python
azimuths = np.arange(0, 180, 22.5)
directional = [bt.experimental_variogram(xy, v, 10.0, 120.0, azimuth=a) for a in azimuths]
model = bt.Variogram.fit_directional(
    directional, [(a, 0) for a in azimuths], ["spherical", "spherical"], weighting="count/gamma"
)
search = bt.Search(radius=80, max_samples=24, min_samples=4, rotation=model.rotation, ratios=(0.5, 1.0))
kriging = bt.BlockKriging(model, search, size=(10, 10), discretization=(5, 5, 1)).fit(xy, v)
inverse = bt.InverseDistance(search, power=2).fit(xy, v)

blocks = bt.BlockModel(origin=(0.5, 0.5), size=(10, 10), count=(26, 30))
blocks = blocks.with_columns({"ok": kriging.predict(blocks), "id": inverse.predict(blocks)})
ok, idw = blocks["ok"], blocks["id"]
print(blocks)
print(f"unestimated blocks: kriging {np.isnan(ok).sum()}, inverse distance {np.isnan(idw).sum()}")
```

</details>

```text
BlockModel  regular, 780 blocks
  count   26 × 30 × 1
  size    10 × 10 × 1
  origin  0.5, 0.5, 0
  bounds  x 0.5 to 260.5, y 0.5 to 300.5, z 0 to 1
  column  type     unit  nulls    min   mean     max
  ok      float64            0  5.602  287.4  1009.9
  id      float64            0   8.81  315.9  1002.2
unestimated blocks: kriging 0, inverse distance 0
```

!!! step "Step 2: Global means against the declustered samples"
    An unbiased model reproduces the declustered mean. `global_bias` compares the block mean with the weighted
    sample mean.

<details><summary>Python</summary>

```python
for name, estimate in (("kriging", ok), ("inverse distance", idw)):
    bias = bt.global_bias(estimate, v, data_weights=weights)
    print(
        f"{name:>16}: blocks {bias['estimate_mean']:.1f} ppm, declustered samples {bias['data_mean']:.1f} ppm, "
        f"bias {bias['relative']:+.1%}"
    )
```

</details>

```text
         kriging: blocks 287.4 ppm, declustered samples 281.6 ppm, bias +2.1%
inverse distance: blocks 315.9 ppm, declustered samples 281.6 ppm, bias +12.2%
```

Kriging is 2.1 % above the declustered mean; inverse distance is 12.2 % above it. That gap needs an
explanation before anything else.

!!! pitfall "Pitfall: checking against the naive mean"
    Against the naive sample mean of 406.7 ppm, inverse distance (315.9 ppm) looks closer than kriging
    (287.4 ppm), and a reviewer might conclude it "honors the data better". The naive mean counts every sample
    in the high-grade clusters at full weight, which is the same error inverse distance makes. Compare with the
    declustered mean.

The two methods weigh a cluster differently. Inverse distance looks only at the distance from the block to
each sample. Kriging also looks at the distances between samples: four samples a few meters apart carry little
more information than one, so they share the weight one sample would get.

<figure class="bt-figure">
--8<-- "svg/w2-cluster-weights.svg"
<figcaption><b>Figure 1.</b> One sample 40 m west of a block, four clustered samples 40 to 48 m east of it.
Inverse distance gives the cluster 0.77 of the weight because it has four samples; ordinary kriging (spherical
variogram, 100 m range, nugget 20 % of the sill) gives it 0.54, about as much as the one sample (0.46). Where the
clusters sit on high grades, inverse distance pulls the estimates up.</figcaption>
</figure>

!!! step "Step 3: Map the difference"
    A difference map (inverse distance minus kriging, per block) shows where the models disagree. Plot it on a
    diverging scale centered on zero, with the samples on top.

<details><summary>Python</summary>

```python
extent = (0.5, 260.5, 0.5, 300.5)
difference = idw - ok
fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), layout="constrained")
norm = PowerNorm(0.5, vmin=0, vmax=1200)
for ax, image, title in ((axes[0], ok, "Ordinary kriging"), (axes[1], idw, "Inverse distance")):
    im = ax.imshow(blocks.grid(image)[0], origin="lower", extent=extent, norm=norm)
    map_axes(ax, title)
fig.colorbar(im, ax=axes[:2], shrink=0.8, label="V (ppm)")
limit = np.abs(difference).max()
dm = axes[2].imshow(
    blocks.grid(difference)[0],
    origin="lower",
    extent=extent,
    cmap="RdBu_r",
    norm=TwoSlopeNorm(0, -limit, limit),
)
axes[2].scatter(samples.x, samples.y, s=3, color=INK, linewidths=0)
map_axes(axes[2], "Inverse distance − kriging")
fig.colorbar(dm, ax=axes[2], shrink=0.8, label="ppm")
save(fig, "maps")

higher = difference > 0
print(
    f"inverse distance is higher in {higher.mean():.0%} of the blocks; mean difference {difference.mean():+.1f} ppm"
)
```

</details>

```text
inverse distance is higher in 74% of the blocks; mean difference +28.5 ppm
```

![maps](maps.png)

Inverse distance is higher in 74 % of the blocks, by 28.5 ppm on average. The largest differences lie at the
edges of the dense clusters, where a block's search reaches a few isolated samples and many clustered ones, the
case Figure 1 draws.

!!! step "Step 4: Block against block"
    A scatter of one model against the other, block by block, separates a shift (points off the 1:1 line on
    one side) from scatter (points spread around it).

<details><summary>Python</summary>

```python
fig, ax = plt.subplots(figsize=(4.8, 4.6), layout="constrained")
ax.scatter(ok, idw, s=6, color=ACCENT, alpha=0.5, linewidths=0)
ax.plot([0, 1300], [0, 1300], color=GRAY, lw=1, label="1:1")
ax.set(xlim=(0, 1300), ylim=(0, 1300), xlabel="Kriging (ppm)", ylabel="Inverse distance (ppm)")
ax.set_aspect("equal")
ax.set_title("Block against block")
ax.legend(loc="upper left")
save(fig, "scatter")
print(f"correlation {np.corrcoef(ok, idw)[0, 1]:.3f}")
for low, high in ((0, 400), (400, 800), (800, 1300)):
    band = (ok >= low) & (ok < high)
    print(
        f"kriging {low}-{high} ppm: {band.sum():3} blocks, inverse distance higher in {(idw > ok)[band].mean():.0%}, "
        f"mean difference {difference[band].mean():+.1f} ppm"
    )
```

</details>

```text
correlation 0.963
kriging 0-400 ppm: 608 blocks, inverse distance higher in 76%, mean difference +29.4 ppm
kriging 400-800 ppm: 163 blocks, inverse distance higher in 71%, mean difference +27.0 ppm
kriging 800-1300 ppm:   9 blocks, inverse distance higher in 33%, mean difference -7.2 ppm
```

![scatter](scatter.png)

The two models rank the blocks alike (correlation 0.963), yet the cloud sits off the 1:1 line. Of the 608
blocks kriged below 400 ppm, inverse distance puts 76 % higher, by 29.4 ppm on average; of the 9 above 800 ppm,
it puts 67 % lower. Inverse distance lifts the low-grade blocks whose neighborhoods reach into a high-grade
cluster.

!!! step "Step 5: Swaths against the declustered samples"
    A swath plot averages the blocks and the samples in slices (here 20 m) along one axis. It shows where along
    the deposit each model departs from the data.

<details><summary>Python</summary>

```python
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
for ax, axis, label in ((axes[0], "x", "Easting (m)"), (axes[1], "y", "Northing (m)")):
    series = [
        bt.swath(samples, "V", 20.0, axis=axis, weights=weights),
        bt.swath(blocks, "ok", 20.0, axis=axis),
        bt.swath(blocks, "id", 20.0, axis=axis),
    ]
    bt.plot.swath(series, labels=["Declustered samples", "Kriging", "Inverse distance"], ax=ax)
    for line, color in zip(ax.lines, (GRAY, ACCENT, HIGHLIGHT), strict=True):
        line.set_color(color)
    ax.legend()
    ax.set(xlabel=label, ylabel="V (ppm)")
save(fig, "swaths")
```

</details>

![swaths](swaths.png)

Kriging follows the declustered samples slice by slice. Inverse distance runs above both over most of the
deposit, so its bias is not a local artifact.

!!! step "Step 6: Tonnage and grade above cutoffs"
    `compare_models` takes the block model, the columns to compare and a list of cutoffs, and returns for each
    cutoff and model the tonnage, mean grade and metal above it, plus each one's difference from a `reference`
    model. Without a density each block weighs its volume (here its area, 100 m²).

<details><summary>Python</summary>

```python
table = bt.compare_models(blocks, ["ok", "id"], [0, 200, 400, 600], reference="ok")
print(
    f"{'cutoff':>6} {'model':>5} {'area above (m²)':>16} {'mean V':>7} {'area diff':>10} {'grade diff':>11}"
)
for row in zip(
    *(table[c] for c in ("cutoff", "model", "tonnage", "mean_grade", "tonnage_diff", "grade_diff"))
):
    cutoff, name, tonnage, grade, dt, dg = row
    print(f"{cutoff:6.0f} {name:>5} {tonnage:16,.0f} {grade:7.1f} {dt:+10.1%} {dg:+11.1%}")
```

</details>

```text
cutoff model  area above (m²)  mean V  area diff  grade diff
     0    ok           78,000   287.4      +0.0%       +0.0%
     0    id           78,000   315.9      +0.0%       +9.9%
   200    ok           51,500   372.2      +0.0%       +0.0%
   200    id           55,700   389.4      +8.2%       +4.6%
   400    ok           17,200   552.3      +0.0%       +0.0%
   400    id           20,300   559.1     +18.0%       +1.2%
   600    ok            5,300   714.2      +0.0%       +0.0%
   600    id            6,300   714.0     +18.9%       -0.0%
```

The shift carries into selection: at 200 ppm inverse distance reports 8.2 % more area above cutoff than
kriging, at a 4.6 % higher grade. The next tutorial turns this into tonnes and metal.

!!! step "Step 7: Cross-validation"
    Leave-one-out cross-validation re-estimates each sample from its neighbors with itself left out. A small mean
    error, a low RMSE and a slope of actual on estimate near 1 mark the better estimator.

<details><summary>Python</summary>

```python
point_kriging = bt.OrdinaryKriging(model, search).fit(xy, v)
print(f"{'':>16}  mean error   RMSE   corr  slope")
for name, estimator in (("kriging", point_kriging), ("inverse distance", inverse)):
    cv = estimator.cross_validate()
    print(f"{name:>16}  {cv.mean_error:10.1f} {cv.rmse:6.1f} {cv.correlation:6.3f} {cv.slope:6.2f}")
```

</details>

```text
                  mean error   RMSE   corr  slope
         kriging         8.9  166.0  0.794   1.05
inverse distance        47.4  187.8  0.745   1.01
```

Kriging wins on mean error and RMSE: 8.9 against 47.4 ppm, and 166.0 against 187.8. The slopes are both near 1
(1.05 for kriging, 1.01 for inverse distance), so neither is clearly conditionally biased here: the inverse distance
error is a shift, not a smoothing. (Cross-validation uses point kriging, since the samples are points.)

!!! check "Check before you move on"
    The metal survey has an exhaustive grid, so the true block averages are known here. They are never known on a real
    deposit; they serve only to test the decision made from the samples.

<details><summary>Python</summary>

```python
truth = bt.datasets.clustered_metal_survey_exhaustive()["V"].reshape(300, 260)
true_blocks = truth.reshape(30, 10, 26, 10).mean(axis=(1, 3)).ravel()
print(f"true block mean {true_blocks.mean():.1f} ppm")
for name, estimate in (("kriging", ok), ("inverse distance", idw)):
    c = bt.compare(estimate, true_blocks)
    print(
        f"{name:>16}: mean {estimate.mean():.1f} ppm ({estimate.mean() / true_blocks.mean() - 1:+.1%}), "
        f"RMSE {c['rmse']:.1f} ppm, correlation {c['correlation']:.3f}"
    )
```

</details>

```text
true block mean 279.5 ppm
         kriging: mean 287.4 ppm (+2.8%), RMSE 106.0 ppm, correlation 0.871
inverse distance: mean 315.9 ppm (+13.0%), RMSE 123.2 ppm, correlation 0.835
```

The truth agrees with the samples: kriging overstates the mean by 2.8 %, inverse distance by 13.0 %, and the
kriged blocks are closer to the true ones (RMSE 106.0 against 123.2 ppm). Part of kriging's 2.8 % comes from the
declustered mean itself: 281.6 ppm is 0.8 % above the true 279.5 ppm, and no check against the samples can see
that.

## The decision

Keep the kriging. Every check made from the samples alone pointed the same way, except the cross-validation
slope, which is near 1 for both:

<div class="bt-compare" markdown>

| Check | Ordinary kriging | Inverse distance |
|---|---|---|
| Mean against declustered samples | +2.1 % | +12.2 % |
| Blocks above the other model | 26 % | 74 % |
| Swaths | Follow the samples | Above them over most slices |
| Cross-validation RMSE, slope | 166.0 ppm, 1.05 | 187.8 ppm, 1.01 |

</div>

Inverse distance ignores sample clustering, so the scoping model is biased high wherever
a block's neighborhood includes a dense cluster of high-grade drilling. [Grade-tonnage curves and the change in contained metal](../../14-workflows/06-grade-tonnage-and-metal/README.md)
turns this difference into tonnes, grade and metal at a cutoff.

Full script: [`example_14_05.py`](example_14_05.py)
