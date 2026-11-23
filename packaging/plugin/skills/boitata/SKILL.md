---
name: boitata
description: How to write correct code with boitatá (`import boitata as bt`), the Rust-core Python geostatistics library - drill holes, compositing, block models, declustering, transforms, variograms, kriging, simulation, recoverable resources and model checks. Use whenever code imports `boitata`, or the user asks for geostatistics or resource-estimation work in Python and boitatá is installed or wanted.
---

# boitatá

boitatá is imported as `bt`. Install it with `pip install "boitata[all]"` (Python ≥ 3.11).

```python
import boitata as bt
```

## Look it up before you write it

Do not write a boitatá call from memory. The installed package carries its own reference, and it matches the
installed version exactly:

```sh
python -c "import boitata, pathlib; print(boitata.__version__, pathlib.Path(boitata.__file__).with_name('_boitata.pyi'))"
```

- Search that `_boitata.pyi` stub for the class or function to get its exact signature.
- `python -c "import boitata as bt; help(bt.OrdinaryKriging.fit)"` prints the NumPy-style docstring, with every
  argument, its unit and its default.
- `bt.__all__` lists every public name; `dir(bt.datasets)` and `dir(bt.plot)` list the datasets and the plots.
- The docs at https://cratongen.github.io/boitata/ hold a worked example for most tasks. The page
  https://cratongen.github.io/boitata/guide/finder/ maps a question to the example that answers it.

If a name is not in `bt.__all__`, it does not exist. Say so and offer the closest one that does; do not invent it.

## Kinds of object

Ask which kind you hold, and the calls follow.

| Kind | Examples | You call | Saves as |
| --- | --- | --- | --- |
| Container | `Table`, `PointSet`, `Drillholes`, `BlockModel`, `Mesh`, `Polylines` | `with_column`, `filter`, `["V"]`, `coords` | Parquet |
| Value object | `Variogram`, `Structure`, `Search`, `Categories`, `HighGrade` | properties, `to_json` | JSON |
| Transform | `NormalScore`, `Capping`, `PPMT`, `PCA`, `MAF` | `fit`, `transform`, `inverse_transform` | JSON |
| Estimator | `OrdinaryKriging`, `BlockKriging`, `InverseDistance` | `fit`, `predict`, `cross_validate` | Parquet |
| Simulator | `SGS`, `DSS`, `SIS`, `TurningBands` | `fit`, `simulate` | Parquet |
| Function | `describe`, `swath`, `experimental_variogram` | one call | its result |

One run through every kind:

```python
samples = bt.datasets.clustered_metal_survey()
experimental = bt.experimental_variogram(samples, "V", 10.0, 120.0)
variogram = experimental.fit("spherical")
search = bt.Search(radius=60, max_samples=24, min_samples=4)
grid = bt.BlockModel(origin=(2.5, 2.5), size=(5, 5), count=(52, 60))
kriging = bt.OrdinaryKriging(variogram, search).fit(samples, "V")
estimate, variance = kriging.predict(grid, return_variance=True)
grid = grid.with_column("V", estimate).with_column("V_variance", variance)
check = kriging.cross_validate()
fig, ax = bt.plot.histogram("V", data=grid)
```

## Rules that hold everywhere

- **Options go to the constructor, data to `fit`, targets to `predict`, `transform` or `simulate`.** `fit` returns
  the object, so calls chain.
- **Options are keyword-only.** `bt.Search(60, 24)` raises `TypeError`; write `bt.Search(radius=60, max_samples=24)`.
- **Containers never change in place.** `with_column`, `with_columns` and `filter` return a new container, so assign
  the result: `grid = grid.with_column(...)`.
- **A column name stands for a column** wherever the call can see the container: `kriging.fit(samples, "V")`,
  `bt.describe("V", data=samples)`.
- **Results are NumPy arrays in target order.** For a block model that is the row order, so the array goes straight
  into `with_column`. A target the search could not fill is `NaN`. `predict(..., diagnostics=True)` returns a
  `Table` with slope, efficiency and sample counts per target.
- **Geometry is 3D.** `(n, 2)` coordinates get `z = 0`; a 2D grid is a `BlockModel` with one block in z. Axes are
  right-handed with z up.
- **Ranges are `(major, semi-major, minor)`; a rotation is `(azimuth, dip, rake)` in degrees**, azimuth clockwise
  from north, dip positive down. The variogram, the search and the block model share that triple.
- **A `BlockModel` origin is the outer corner of the first block**, not its center. Rows run along x, then y, then z.
- **Names are spelled out**, in American spelling: `OrdinaryKriging`, `NormalScore`, `experimental_variogram`. Only
  SGS, DSS, SIS, PCA, MAF and CRS stay short.
- **Simulations take `seed`**, and the same seed gives the same realizations whatever the thread count.
- **These are not scikit-learn estimators.** They take coordinates plus one column of values, have no `get_params`
  and do not drop into a scikit-learn `Pipeline`.

## Missing values

Readers turn sentinels (`-99`, `-999`, `1e21`, `NA`, `NULL`, empty cells) into nulls, which show as `NaN` in NumPy.
Statistics such as `describe` skip them. Estimators, transforms and variograms refuse them with
`InvalidInput: values must be finite; drop missing values first`. Drop the rows yourself, and tell the user how
many went:

```python
import numpy as np

assayed = samples.filter(~np.isnan(samples["V"]))
```

## Errors

boitatá's own errors derive from `bt.BoitataError` and from a builtin: `InvalidInput` is a `ValueError`,
`MissingColumn` a `KeyError`, `FileError` an `OSError`. `MissingColumn` lists the columns the container has. Read
the message before changing the code; it names the argument at fault.

## Saving

Parameters go to JSON: `variogram.to_json()` and `bt.Variogram.from_json(text)`, the same for a fitted transform.
Columns go to Parquet: `bt.write_parquet(path, data)` and `bt.read_parquet(path)` for containers,
`obj.to_parquet(path)` and `Class.from_parquet(path)` for fitted estimators and simulation results. `write_csv`
drops block size, rotation, CRS and layout, so keep working files in Parquet.

## Data

`bt.datasets` generates every dataset from a seed, offline. Use one for a demonstration or a test in place of
inventing numbers. Grouping, joining and pivoting belong to Polars or pandas: `data.to_polars()`,
`data.to_pandas()`.

## Write it fast

Correct boitatá code can still repeat work the library does in one call, or hold every realization, when it
works around the library. Check each of these before you write a call.

### Do not keep realizations nobody reads

`simulate` returns a summary, and each realization is freed once it has been counted. `keep=True` holds all
`n` realizations as an `(n, targets)` array. Before you write `keep=`, find out what the user does with the
realizations. If the request does not say, ask.

| The user wants | Write | Realizations kept |
| --- | --- | --- |
| Mean, variance, standard deviation, CV per block | nothing: `summary.mean`, `summary.std`, `summary.cv` | none |
| Probability or mean grade above a cutoff | `cutoffs=[0.5]` | none |
| P10, P50, P90 per block | `quantiles=[0.1, 0.5, 0.9]` | none returned |
| Grade-tonnage curves with their uncertainty | `grade_tonnage_cutoffs=[...]`, `density=` | none |
| Results at SMU or panel support | `blocks=coarser_model` | none |
| Results per mine-plan period or per zone | `groups="PERIOD"` | none |
| A few realizations to plot or check | `keep=[0, 1, 2]` | those |
| Every realization, to feed another simulation or to save them all | `keep=True` | all |

- `quantiles=` and `tolerances=` hold every value while they accumulate, so they cost the memory of `keep=True`.
  Ask for them only when the user needs them.
- Save the result with `summary.to_parquet(path)`. Do not write realizations to one file each.
- Never call `simulate(n=1)` in a Python loop to collect realizations. One call with `n=` shares the work
  between them.
- Leave `memory`, `batch` and `path` at their defaults. They are sized from the machine and the targets.
- **Use the `n` the user gave.** Without one, keep the default of 100 and say so. Do not raise it "to be safe";
  the run time grows with it.
- **Let `simulate` do the averaging.** A result per panel, per period, per zone or in a moving window comes from
  `blocks=`, `groups=` or `window=`. Never keep every realization to average it in NumPy afterwards.
- **Rank realizations without keeping them.** `summary.realization_mean` is the mean of each realization. Pick
  the low, middle and high ones from it, then call `simulate` again with the same `seed` and `keep=[those]`:
  realization `k` depends only on the seed and `k`, so it comes back identical.
- **A representative handful** comes from `picked = bt.select_realizations(summary, 5)` on a summary simulated
  with `keep=`. `picked` indexes `summary.kept`, and the rows are `summary.realizations[picked]`.

### Keep the shared path

On a regular or masked `BlockModel`, SGS and DSS follow one multigrid path by default, so each node's neighbors
and kriging weights are found once for the batch. The default uses a random path per realization when the inputs
cannot share one. `path="shared"` raises `InvalidInput` and names the cause.

These inputs leave the shared path:

- targets other than a regular or masked `BlockModel`: points, `grid.coords`, a sub-blocked model;
- `bt.Search(octant=True)`, `sectors=`, `high_grade=`, `soft=` or `min_holes=`;
- simulated domains, an `(n, targets)` array passed as `domains=`.

DSS also leaves the shared path for `anisotropy=`, a trend, domains fitted on the samples, and a secondary
variable. SGS with `anisotropy=` stays on the shared path on a regular or masked block model: a node's anisotropy
does not change between realizations.

Add one of these only when the user asked for it or the geology needs it, and say when the run uses a random path.

### Pass boitatá containers, not arrays pulled out of them

- **Targets are the `BlockModel` itself**: `simulate(grid)`, `predict(grid)`. `simulate(grid.coords)` gives the
  same kind of answer, but the blocks arrive as loose points, so the simulation falls back to a random path per
  realization and loses the shared path that finds each node's neighbors and weights once for all of them.
- **Blocks inside a domain are a masked model**: `grid.filter(mask)`, not `grid.coords[mask]`.
- **Samples are the `PointSet` or `Drillholes`, and values are column names**: `fit(samples, "Au")`,
  `domain_column="ZONE"`, `holes="HOLE_ID"`, `trend="TREND"`. Do not rebuild coordinate and value arrays by hand.
- **Domains go in one call** through `domain_column=`. Do not loop over the domains in Python, fitting and
  predicting each one.
- **Read straight into a container** with the boitatá readers (`bt.read_parquet`, `bt.read_csv`). Do not load a
  file with pandas and convert it. Go to Polars or pandas (`to_polars()`, `to_pandas()`) only for grouping,
  joining and pivoting, at the end.
- **Working files are Parquet.** CSV is for exchange with other software.
- **A model larger than memory is read in chunks**: `bt.BlockModelFile(path).chunks(columns=[...])`, or
  `bt.map_blocks(path, out, func)` to compute columns chunk by chunk. Do not load it whole. Name in `columns=`
  only the columns the code reads; the default reads all of them.

### One call, not a Python loop

Every estimator, simulator and transform takes all its rows in one call and runs them in parallel in Rust. A
Python `for` over blocks, samples, realizations or domains calls that function once per row.

- **Fit once.** Reuse the fitted object for every `predict` or `simulate`. To try another search, call
  `kriging.with_search(search)`: it returns a copy that keeps the fitted samples. To come back to a fit in another
  session, save it with `to_parquet` and load it with `from_parquet`.
- **Estimate only the blocks that matter.** Filter the model to the domain or the pit first,
  `inside = grid.filter(mask)`, then `predict(inside)`. Do not estimate every block and mask the result.

### Do not promise a speed

Give the user a time or a speedup only after you ran the code and timed it. Otherwise say it was not measured.

## Hand it to a sibling

boitata is one of a family of standalone libraries for mining and geoscience at https://github.com/cratongen.
None imports another. They pass NumPy arrays, and tables pass through Arrow, so pandas, polars and pyarrow
work in between.

| Library | Import | What it does |
| --- | --- | --- |
| boitata | `import boitata as bt` | Geostatistics: drill holes, compositing, block models, variograms, kriging, simulation |
| segyrs | `import segyrs` | Read, write and slice SEG-Y files, including files larger than memory |
| transiograms | `import transiograms as tg` | Markov chains, hidden Markov models, transiograms and categorical simulation |
| wireframes | `import wireframes as wf` | Solids, surfaces and strings: read, write, measure and combine |

<!-- Below this line: what boitata hands to each sibling and takes from it, with one short example per neighbour.
Only calls that exist today in both libraries, checked against ../<sibling>/python/<pkg>/*.pyi. -->

**wireframes.** A mesh crosses as `coords` of shape `(n, 3)` and `triangles` of shape `(m, 3)`. A point set
crosses as `coords` plus its columns. `to_pyarrow()` is the Arrow table. `wf.PointSet` and `wf.Mesh` take the
NumPy arrays, and `coords` with `triangles` come back into `bt.Mesh`.

```python
import numpy as np
import boitata as bt
import wireframes as wf

samples = bt.datasets.clustered_metal_survey()
table = samples.to_pyarrow()
points = wf.PointSet(samples.coords, {"V": np.asarray(table.column("V"))})
lens = bt.datasets.stacked_sulphide_lenses()["lens_1"]
solid = wf.Mesh(lens.coords, lens.triangles)
back = bt.Mesh(solid.coords, solid.triangles)
```

**transiograms.** Lithology intervals cross as arrays. Encode text with `tg.Categories.from_labels` before
`MarkovChain.fit`. The default `direction="up"` reads each hole from its base, so the overburden that caps every
hole has no transition out of it; `on_empty_row="uniform"` lets the fit run. `simulate_beds` returns integer
codes in that category order.

```python
import numpy as np
import boitata as bt
import transiograms as tg

lith = bt.datasets.stacked_sulphide_lenses()["lithology"]
labels = np.asarray(lith["LITH"])
categories = tg.Categories.from_labels(labels)
codes = categories.encode(labels)
chain = tg.MarkovChain(on_empty_row="uniform").fit(
    codes,
    holes=np.asarray(lith["HOLE_ID"]),
    from_=np.asarray(lith["FROM"], dtype=float),
    to=np.asarray(lith["TO"], dtype=float),
)
beds = chain.simulate_beds(4, n=1, seed=0)
names = np.asarray(categories.names)[beds.ravel()]
```

**segyrs.** A block-model column whose flat order is `ix + nx * (iy + ny * iz)` crosses as a `(traces, samples)`
float32 array: reshape the column to `(nz, ny, nx)`, then transpose. `segyrs.create` writes it.
`segyrs.open(path).numpy()` returns the samples, and `with_column` takes the flat column back. For `seismic_cube` the sample
interval is 4 ms, so pass 4000 microseconds.

```python
import numpy as np
import boitata as bt
import segyrs

cube = bt.datasets.seismic_cube()
nx, ny, nz = cube.count
volume = np.asarray(cube["amplitude"]).reshape(nz, ny, nx)
traces = np.ascontiguousarray(volume.reshape(nz, -1).T, dtype=np.float32)
segyrs.create("amplitude.sgy", traces, sample_format="ieee_float32", sample_interval_us=4000)
back = segyrs.open("amplitude.sgy").numpy()
flat = np.asarray(back, dtype=np.float64).T.reshape(-1)
model = bt.BlockModel(cube.origin, cube.size, cube.count).with_column("amplitude", flat)
```

## Before you report a result

Run the code. Then check what the method promises: `cross_validate()` for a kriging plan, the histogram and
variogram of the realizations for a simulation, a swath or a global mean against the declustered samples for a
block model. Report the numbers you got, in the units of the data.
