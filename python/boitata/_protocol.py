"""The ``__minetypes__`` protocol, version 1.

Each boitatá container returns a plain dict of NumPy arrays from ``__minetypes__``, and builds itself
from any object of a matching kind with ``from_minetypes``. Every public function and method also
accepts such an object where it takes a container.
"""

import functools
import inspect
import math
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from boitata import _boitata
from boitata._boitata import BlockModel, Categories, Drillholes, Mesh, PointSet, Polylines, Table
from boitata.errors import InvalidInput

KINDS = (
    "table",
    "categories",
    "grid",
    "block_model",
    "point_set",
    "mesh",
    "polylines",
    "drillholes",
    "intervals",
    "composites",
    "seismic_volume",
    "prestack_volume",
)
OWN = (Table, Categories, BlockModel, PointSet, Polylines, Mesh, Drillholes)
_COLUMN_DTYPES = ("f8", "f4", "i8", "i4", "b1")
_METHODS = ("minimum_curvature", "tangential", "balanced_tangential")


def _bad(message: str) -> InvalidInput:
    return InvalidInput(message)


def _header(kind: str, crs: Any = None, length_unit: Any = None) -> dict[str, Any]:
    return {"protocol": 1, "kind": kind, "crs": crs, "length_unit": length_unit}


def _common(parts: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    return {
        f"{prefix}columns": parts[f"{prefix}columns"],
        f"{prefix}units": parts[f"{prefix}units"],
        f"{prefix}categories": parts[f"{prefix}categories"],
    }


def _empty(prefix: str = "") -> dict[str, Any]:
    return {f"{prefix}columns": {}, f"{prefix}units": {}, f"{prefix}categories": {}}


def table_minetypes(self: Table) -> dict[str, Any]:
    """Protocol dict of kind ``table``.

    Numeric columns without nulls are read-only views of the table's storage. A copy is made for a
    column with nulls (NaN, float64 for integers), for bool and text columns, and for text with
    nulls, which becomes int32 codes with a ``categories`` entry and -1 for null.

    Raises
    ------
    InvalidInput
        When a column holds infinity or has a type the protocol cannot carry, such as a date.
    """
    parts = _boitata._minetypes_parts(self)
    return {**_header("table"), **_common(parts), "rows": parts["rows"]}


def points_minetypes(self: PointSet) -> dict[str, Any]:
    """Protocol dict of kind ``point_set``; ``coords`` is a read-only view, columns as on ``Table``."""
    parts = _boitata._minetypes_parts(self)
    return {**_header("point_set", self.crs, self.length_unit), **_common(parts), "coords": parts["coords"]}


def polylines_minetypes(self: Polylines) -> dict[str, Any]:
    """Protocol dict of kind ``polylines``.

    ``coords``, ``part_offsets``, ``feature_offsets`` and ``closed`` are read-only views; the
    feature attributes are ``columns``, and there are no vertex columns.
    """
    p = _boitata._minetypes_parts(self)
    keys = ("coords", "part_offsets", "feature_offsets", "closed")
    return {
        **_header("polylines", self.crs, self.length_unit),
        **_common(p),
        **{k: p[k] for k in keys},
        **_empty("vertex_"),
    }


def mesh_minetypes(self: Mesh) -> dict[str, Any]:
    """Protocol dict of kind ``mesh``; ``coords`` and the uint32 ``triangles`` are read-only views."""
    p = _boitata._minetypes_parts(self)
    return {
        **_header("mesh", self.crs, self.length_unit),
        **_empty(),
        "coords": p["coords"],
        "triangles": p["triangles"],
        **_common(p, "vertex_"),
        **_common(p, "face_"),
    }


def blocks_minetypes(self: BlockModel) -> dict[str, Any]:
    """Protocol dict of kind ``block_model``.

    A regular model sends its geometry and no coordinates. A masked model's ``index`` and a
    sub-blocked model's ``parent`` are read-only views. Sub-block extents become float32
    ``offset`` (centre) and ``scale`` (size) fractions of the parent cell; those two arrays copy.
    """
    p = _boitata._minetypes_parts(self)
    keys = ("layout", "index", "parent", "offset", "scale", "subgrid")
    geometry = {k: [float(v) for v in p[k]] for k in ("origin", "size", "rotation")}
    return {
        **_header("block_model", self.crs, self.length_unit),
        **_common(p),
        **geometry,
        "count": [int(v) for v in p["count"]],
        **{k: p[k] for k in keys},
    }


def drillholes_minetypes(self: Drillholes) -> dict[str, Any]:
    """Protocol dict of kind ``drillholes``.

    Collars are the first point of each path. The survey dip is negative downward: boitatá stores
    inclination from vertical down and writes ``dip = inclination - 90``. The interval table loses
    rows whose hole has no collar or whose depths are null. Every array copies.

    Raises
    ------
    InvalidInput
        When intervals of one hole overlap or run backwards.
    """
    p = _boitata._minetypes_parts(self)
    keys = ("holes", "coords", "survey", "intervals", "path_coords", "path_depths", "path_offsets", "method")
    return {
        **_header("drillholes", self.crs, self.length_unit),
        **_empty(),
        **{k: p[k] for k in keys},
        "tables": {},
    }


def categories_minetypes(self: Categories) -> dict[str, Any]:
    """Protocol dict of kind ``categories``."""
    colors = self.colors
    return {
        **_header("categories"),
        **_empty(),
        "names": list(self.names),
        "colors": None if colors is None else list(colors),
        "mapping": dict(self.mapping),
        "other": self.other,
    }


def _as_spec(obj: Any) -> dict[str, Any]:
    method = getattr(obj, "__minetypes__", None)
    spec = method() if callable(method) else obj
    if not isinstance(spec, Mapping):
        raise _bad(f"{type(obj).__name__} is not a protocol object: it has no __minetypes__ returning a dict")
    return dict(spec)


def _require(d: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise _bad(f"{where} is missing key {key!r}")
    return d[key]


def _label(d: Mapping[str, Any], key: str) -> str | None:
    value = _require(d, key, "the protocol dict")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _bad(f"key {key!r} must be None or a non-blank string, got {value!r}")
    return value.strip() if key == "length_unit" else value


def _open(obj: Any, accepted: Sequence[str], who: str) -> dict[str, Any]:
    d = _as_spec(obj)
    for key in ("protocol", "kind", "columns", "units", "categories", "crs", "length_unit"):
        _require(d, key, "the protocol dict")
    if isinstance(d["protocol"], bool) or d["protocol"] != 1:
        raise _bad(f"key 'protocol' is {d['protocol']!r}; boitatá reads version 1")
    kind = d["kind"]
    if kind not in KINDS:
        raise _bad(f"key 'kind' names {kind!r}, which is not a protocol kind")
    if kind not in accepted:
        raise _bad(f"{who} takes kind {' or '.join(map(repr, accepted))}, not {kind!r}")
    _label(d, "crs")
    _label(d, "length_unit")
    return d


def _array(value: Any, key: str, dtype: str | None, ndim: int, length: int | None = None) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise _bad(f"key {key!r} must be a NumPy array, got {type(value).__name__}")
    if dtype is not None and value.dtype != np.dtype(dtype):
        raise _bad(f"key {key!r} must have dtype {np.dtype(dtype)}, got {value.dtype}")
    if not value.dtype.isnative:
        raise _bad(f"key {key!r} has a foreign byte order; the protocol needs native-endian arrays")
    if not value.flags.c_contiguous:
        raise _bad(f"key {key!r} must be C-contiguous")
    if value.ndim != ndim or (ndim == 2 and value.shape[1] != 3):
        want = "(n,)" if ndim == 1 else "(n, 3)"
        raise _bad(f"key {key!r} must have shape {want}, got {value.shape}")
    if length is not None and value.shape[0] != length:
        raise _bad(f"key {key!r} has {value.shape[0]} rows; it needs {length}")
    return value


def _finite(value: np.ndarray, key: str) -> None:
    if not np.isfinite(value).all():
        raise _bad(f"key {key!r} must be finite")


def _entry(name: str, entry: Any, where: str) -> list[str]:
    if not isinstance(entry, Mapping):
        raise _bad(f"{where} category {name!r} must be a dict")
    for key in ("names", "colors", "mapping", "other"):
        _require(entry, key, f"{where} category {name!r}")
    names = (
        list(entry["names"])
        if isinstance(entry["names"], Sequence) and not isinstance(entry["names"], str)
        else None
    )
    if not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise _bad(f"{where} category {name!r} needs distinct, non-empty names")
    colors = entry["colors"]
    if colors is not None and (
        isinstance(colors, str)
        or len(colors) != len(names)
        or any(not isinstance(c, str) or not c for c in colors)
    ):
        raise _bad(f"{where} category {name!r} needs one non-empty color per name, or None")
    mapping = entry["mapping"]
    if not isinstance(mapping, Mapping) or any(
        not isinstance(k, str) or k in names or v not in names for k, v in mapping.items()
    ):
        raise _bad(f"{where} category {name!r} mapping must send aliases outside names to a name")
    if entry["other"] is not None and entry["other"] != names[-1]:
        raise _bad(f"{where} category {name!r} other must be None or the last name")
    return names


def _columns(d: Mapping[str, Any], rows: int, prefix: str = "") -> tuple[dict[str, Any], dict[str, str]]:
    """Columns as boitatá values (codes become labels) and their units, checked against the spec."""
    where = f"{prefix}columns" if prefix else "columns"
    columns = _require(d, f"{prefix}columns", "the protocol dict")
    units = _require(d, f"{prefix}units", "the protocol dict")
    categories = _require(d, f"{prefix}categories", "the protocol dict")
    if not all(isinstance(x, Mapping) for x in (columns, units, categories)):
        raise _bad(f"keys {prefix}columns, {prefix}units and {prefix}categories must be dicts")
    out: dict[str, Any] = {}
    for name, values in columns.items():
        if not isinstance(name, str) or not name:
            raise _bad(f"{where} has an empty or non-text column name")
        key = f"{where}[{name!r}]"
        values = _array(values, key, None, 1, rows)
        if name in categories:
            names = _entry(name, categories[name], where)
            if values.dtype != np.int32:
                raise _bad(f"{key} is a code column and must be int32, got {values.dtype}")
            if values.size and (values.min() < -1 or values.max() >= len(names)):
                raise _bad(f"{key} holds a code outside -1 .. {len(names) - 1}")
            if values.size and (values < 0).all():
                out[name] = np.full(rows, np.nan)
            else:
                out[name] = np.array(names + [None], dtype=object)[values].tolist()
        elif values.dtype.kind in "UT":
            out[name] = values.astype(str).tolist()
        elif values.dtype.str[1:] in _COLUMN_DTYPES or values.dtype == np.bool_:
            if values.dtype.kind == "f" and np.isinf(values).any():
                raise _bad(f"{key} holds infinity; use NaN for a missing value")
            out[name] = values
        else:
            raise _bad(f"{key} has dtype {values.dtype}, which the protocol does not allow")
    for name in categories:
        if name not in columns:
            raise _bad(f"{prefix}categories names {name!r}, which is not in {where}")
    for name, unit in units.items():
        if name not in columns:
            raise _bad(f"{prefix}units names {name!r}, which is not in {where}")
        if not isinstance(unit, str) or not unit:
            raise _bad(f"{prefix}units[{name!r}] must be a non-empty string")
    return out, dict(units)


def _with_units(obj: Any, units: Mapping[str, str]) -> Any:
    return obj.with_units(dict(units)) if units else obj


def table_from(obj: Any) -> Table:
    """Table from a protocol object of kind ``table`` or ``intervals``.

    Code columns become text holding their category names, null for -1, so a nullable boolean
    comes back as the text ``"false"`` and ``"true"``.
    An ``intervals`` object gives ``HOLE_ID``, ``FROM`` and ``TO`` before its columns.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("table", "intervals"), "Table.from_minetypes")
    if d["kind"] == "intervals":
        holes = _holes(d)
        data, units = _intervals(d, holes, "the intervals")
        return _with_units(Table(data), units)
    rows = _require(d, "rows", "a table")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
        raise _bad(f"key 'rows' must be an int >= 0, got {rows!r}")
    data, units = _columns(d, rows)
    if not data:
        if rows:
            raise _bad("a boitatá Table holds rows only through columns; this table has rows and no columns")
        return Table({})
    return _with_units(Table(data), units)


def _coords(d: Mapping[str, Any], key: str = "coords") -> np.ndarray:
    coords = _array(_require(d, key, f"a {d['kind']}"), key, "f8", 2)
    _finite(coords, key)
    return coords


def points_from(obj: Any) -> PointSet:
    """PointSet from a protocol object of kind ``point_set`` or ``composites``.

    A composites object keeps ``HOLE_ID``, ``FROM``, ``TO``, ``LENGTH`` and, when set, ``DOMAIN``
    before its columns, with the coordinates at the composite midpoints.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("point_set", "composites"), "PointSet.from_minetypes")
    coords = _coords(d)
    data, units = _columns(d, len(coords))
    if d["kind"] == "composites":
        holes = _holes(d)
        hole, start, end = _rows(d, holes, len(coords), "composites")
        length = _array(_require(d, "length", "composites"), "length", "f8", 1, len(coords))
        if not ((length > 0) & (length <= end - start + 1e-9)).all():
            raise _bad("key 'length' must lie in (0, to_depth - from_depth]")
        lead = {"HOLE_ID": [holes[h] for h in hole.tolist()], "FROM": start, "TO": end, "LENGTH": length}
        domain = d.get("domain")
        if domain is not None:
            domain = _array(domain, "domain", "i4", 1, len(coords))
            names = _entry("domain", _require(d["categories"], "domain", "categories"), "categories")
            if domain.size and (domain.min() < -1 or domain.max() >= len(names)):
                raise _bad(f"key 'domain' holds a code outside -1 .. {len(names) - 1}")
            lead["DOMAIN"] = [None if c < 0 else names[c] for c in domain.tolist()]
            data.pop("domain", None)
        clash = sorted(set(lead) & set(data))
        if clash:
            raise _bad(f"composites columns {clash} clash with the names boitatá gives the composite keys")
        data = {**lead, **data}
    points = PointSet(coords, data or None, crs=d["crs"], length_unit=_label(d, "length_unit"))
    return _with_units(points, units)


def _triple(d: Mapping[str, Any], key: str, positive: bool = False) -> list[float]:
    value = _require(d, key, f"a {d['kind']}")
    try:
        values = [float(v) for v in value]
    except (TypeError, ValueError):
        raise _bad(f"key {key!r} must be 3 numbers, got {value!r}") from None
    if len(values) != 3 or not all(math.isfinite(v) for v in values) or (positive and min(values) <= 0):
        rule = "finite and > 0" if positive else "finite"
        raise _bad(f"key {key!r} must be 3 numbers, each {rule}; got {value!r}")
    return values


def _count(d: Mapping[str, Any]) -> list[int]:
    value = _require(d, "count", f"a {d['kind']}")
    if (
        isinstance(value, (str, bytes))
        or len(value) != 3
        or any(isinstance(v, bool) or int(v) != v or v < 1 for v in value)
    ):
        raise _bad(f"key 'count' must be 3 integers, each >= 1; got {value!r}")
    count = [int(v) for v in value]
    if math.prod(count) > 2**63 - 1:
        raise _bad("key 'count' gives more cells than a signed 64-bit integer holds")
    return count


def blocks_from(obj: Any) -> BlockModel:
    """BlockModel from a protocol object of kind ``grid`` or ``block_model``.

    ``origin`` is the minimum corner of cell ``(0, 0, 0)``, as boitatá stores it. Sub-block
    ``offset`` and ``scale`` widen to float64 extents ``c - s/2``, ``c + s/2``, clipped to the cell.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("grid", "block_model"), "BlockModel.from_minetypes")
    origin, size, rotation = _triple(d, "origin"), _triple(d, "size", positive=True), _triple(d, "rotation")
    count = _count(d)
    cells = math.prod(count)
    labels = {"crs": d["crs"], "length_unit": _label(d, "length_unit")}
    layout = "regular" if d["kind"] == "grid" else _require(d, "layout", "a block_model")
    if layout == "regular":
        data, units = _columns(d, cells)
        model = BlockModel(origin, size, count, rotation=tuple(rotation), attributes=data or None, **labels)
    elif layout == "masked":
        index = _array(_require(d, "index", "a masked block_model"), "index", "u8", 1)
        if index.size and ((np.diff(index.astype(np.int64)) <= 0).any() or index[-1] >= cells):
            raise _bad(f"key 'index' must be strictly increasing and below {cells}")
        data, units = _columns(d, len(index))
        model = BlockModel(
            origin, size, count, rotation=tuple(rotation), attributes=data or None, index=index, **labels
        )
    elif layout == "subblocked":
        parent = _array(_require(d, "parent", "a subblocked block_model"), "parent", "u8", 1)
        n = len(parent)
        offset = _array(_require(d, "offset", "a subblocked block_model"), "offset", "f4", 2, n)
        scale = _array(_require(d, "scale", "a subblocked block_model"), "scale", "f4", 2, n)
        if n and ((np.diff(parent.astype(np.int64)) < 0).any() or parent[-1] >= cells):
            raise _bad(f"key 'parent' must be non-decreasing and below {cells}")
        _finite(offset, "offset")
        _finite(scale, "scale")
        c, s = offset.astype(np.float64), scale.astype(np.float64)
        if ((c <= 0) | (c >= 1)).any():
            raise _bad("key 'offset' must lie strictly between 0 and 1 on each axis")
        if ((s <= 0) | (s > 1)).any():
            raise _bad("key 'scale' must lie in (0, 1] on each axis")
        lo, hi = c - 0.5 * s, c + 0.5 * s
        if (lo < -1e-6).any() or (hi > 1 + 1e-6).any():
            raise _bad("keys 'offset' and 'scale' put a sub-block outside its parent cell")
        subgrid = d.get("subgrid")
        if subgrid is not None:
            if len(subgrid) != 3 or any(
                isinstance(m, bool) or int(m) != m or not 1 <= m <= 2**32 - 1 for m in subgrid
            ):
                raise _bad(f"key 'subgrid' must be None or 3 integers in 1 .. 2^32-1, got {subgrid!r}")
            subgrid = tuple(int(m) for m in subgrid)
            m = np.array(subgrid, dtype=np.float64)
            edges = np.concatenate([lo * m, hi * m])
            if (np.abs(edges - np.round(edges)) > 1e-5).any():
                raise _bad(f"keys 'offset' and 'scale' do not align with subgrid {subgrid}")
        data, units = _columns(d, n)
        extents = np.clip(np.hstack([lo, hi]), 0.0, 1.0)
        model = BlockModel.subblocked(
            origin,
            size,
            count,
            parent,
            extents,
            rotation=tuple(rotation),
            subgrid=subgrid,
            attributes=data or None,
            **labels,
        )
    else:
        raise _bad(f"key 'layout' must be 'regular', 'masked' or 'subblocked', got {layout!r}")
    return _with_units(model, units)


def _offsets(d: Mapping[str, Any], key: str, end: int) -> np.ndarray:
    offsets = _array(_require(d, key, f"a {d['kind']}"), key, "u4", 1)
    if (
        not offsets.size
        or offsets[0] != 0
        or offsets[-1] != end
        or (np.diff(offsets.astype(np.int64)) < 0).any()
    ):
        raise _bad(f"key {key!r} must start at 0, end at {end} and not decrease")
    return offsets


def polylines_from(obj: Any) -> Polylines:
    """Polylines from a protocol object of kind ``polylines``.

    boitatá polylines carry feature attributes only, so vertex columns are dropped with a warning.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("polylines",), "Polylines.from_minetypes")
    coords = _coords(d)
    parts = _offsets(d, "part_offsets", len(coords))
    features = _offsets(d, "feature_offsets", len(parts) - 1)
    closed = _array(_require(d, "closed", "a polylines"), "closed", "b1", 1, len(parts) - 1)
    sizes = np.diff(parts.astype(np.int64))
    short = np.flatnonzero(sizes < np.where(closed, 3, 2))
    if short.size:
        p = int(short[0])
        raise _bad(f"part {p} has {sizes[p]} vertices; open parts need 2 and closed parts 3")
    data, units = _columns(d, len(features) - 1)
    vertex, _ = _columns(d, len(coords), "vertex_")
    if vertex:
        warnings.warn(
            f"boitatá Polylines have no vertex attributes; dropped {sorted(vertex)}",
            UserWarning,
            stacklevel=3,
        )
    owner = np.repeat(np.arange(len(features) - 1), np.diff(features.astype(np.int64)))
    lines = Polylines(
        [coords[a:b] for a, b in zip(parts[:-1].tolist(), parts[1:].tolist(), strict=True)],
        closed=closed.tolist(),
        features=owner.tolist(),
        attributes=data or ({} if len(features) > 1 else None),
        crs=d["crs"],
        length_unit=_label(d, "length_unit"),
    )
    return _with_units(lines, units)


def mesh_from(obj: Any) -> Mesh:
    """Mesh from a protocol object of kind ``mesh``, with its vertex and face columns.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("mesh",), "Mesh.from_minetypes")
    coords = _coords(d)
    triangles = _array(_require(d, "triangles", "a mesh"), "triangles", "u4", 2)
    if triangles.size and triangles.max() >= len(coords):
        raise _bad(f"key 'triangles' indexes a vertex at or past {len(coords)}")
    vertex, _ = _columns(d, len(coords), "vertex_")
    face, _ = _columns(d, len(triangles), "face_")
    mesh = Mesh(coords, triangles.astype(np.int64), crs=d["crs"], length_unit=_label(d, "length_unit"))
    for name, values in vertex.items():
        mesh = mesh.with_vertex_column(name, values)
    for name, values in face.items():
        mesh = mesh.with_face_column(name, values)
    return mesh


def _holes(d: Mapping[str, Any]) -> list[str]:
    holes = _require(d, "holes", f"a {d['kind']}")
    if isinstance(holes, (str, bytes)) or not isinstance(holes, Sequence):
        raise _bad("key 'holes' must be a sequence of hole ids")
    holes = list(holes)
    if any(not isinstance(h, str) or not h for h in holes) or len(set(holes)) != len(holes):
        raise _bad("key 'holes' must hold distinct, non-empty strings")
    return holes


def _rows(d: Mapping[str, Any], holes: list[str], n: int | None, where: str) -> tuple[np.ndarray, ...]:
    hole = _array(_require(d, "hole_index", where), "hole_index", "i4", 1, n)
    n = len(hole)
    start = _array(_require(d, "from_depth", where), "from_depth", "f8", 1, n)
    end = _array(_require(d, "to_depth", where), "to_depth", "f8", 1, n)
    if n and (hole.min() < 0 or hole.max() >= len(holes)):
        raise _bad(f"key 'hole_index' of {where} must lie in [0, {len(holes)})")
    _finite(start, "from_depth")
    _finite(end, "to_depth")
    if (start < 0).any() or (end <= start).any():
        raise _bad(f"{where} need 0 <= from_depth < to_depth on each row")
    return hole, start, end


def _intervals(d: Mapping[str, Any], holes: list[str], where: str) -> tuple[dict[str, Any], dict[str, str]]:
    hole, start, end = _rows(d, holes, None, where)
    order = np.lexsort((start, hole))
    if (order != np.arange(len(hole))).any():
        raise _bad(f"rows of {where} must be sorted by (hole_index, from_depth)")
    same = hole[1:] == hole[:-1]
    if (same & (start[1:] < end[:-1] - 1e-9)).any():
        h = int(hole[1:][same & (start[1:] < end[:-1] - 1e-9)][0])
        raise _bad(f"intervals of hole {holes[h]!r} in {where} overlap")
    data, units = _columns(d, len(hole))
    lead = {"HOLE_ID": [holes[h] for h in hole.tolist()], "FROM": start, "TO": end}
    clash = sorted(set(lead) & set(data))
    if clash:
        raise _bad(f"columns {clash} of {where} clash with the names boitatá gives hole, from and to")
    return {**lead, **data}, units


def drillholes_from(obj: Any) -> Drillholes:
    """Drillholes from a protocol object of kind ``drillholes``.

    The holes follow ``path_coords`` as given, so no desurvey runs again. The survey is kept, with
    the protocol dip (negative downward) stored as inclination ``dip + 90``. The primary
    ``intervals`` become the interval table, with ``HOLE_ID``, ``FROM`` and ``TO`` first; with
    no primary table and one entry in ``tables``, that entry does. Collar columns and further
    tables are dropped with a warning.

    Raises
    ------
    InvalidInput
        When the dict breaks a key, dtype, shape, contiguity or endian rule, naming the key.
    """
    d = _open(obj, ("drillholes",), "Drillholes.from_minetypes")
    holes = _holes(d)
    coords = _array(_require(d, "coords", "a drillholes"), "coords", "f8", 2, len(holes))
    _finite(coords, "coords")
    xyz = _coords(d, "path_coords")
    depths = _array(_require(d, "path_depths", "a drillholes"), "path_depths", "f8", 1, len(xyz))
    _finite(depths, "path_depths")
    offsets = _offsets(d, "path_offsets", len(xyz))
    if len(offsets) != len(holes) + 1:
        raise _bad(f"key 'path_offsets' needs {len(holes) + 1} entries, one per hole plus one")
    for h, (a, b) in enumerate(zip(offsets[:-1].tolist(), offsets[1:].tolist(), strict=True)):
        if b - a < 2:
            raise _bad(f"hole {holes[h]!r} has {b - a} path vertices; each hole needs 2")
        if depths[a] != 0 or (np.diff(depths[a:b]) <= 0).any():
            raise _bad(f"path_depths of hole {holes[h]!r} must start at 0 and increase")
    method = _require(d, "method", "a drillholes")
    if method not in _METHODS:
        raise _bad(f"key 'method' must be one of {_METHODS}, got {method!r}")
    survey = _require(d, "survey", "a drillholes")
    stations = None
    if survey is not None:
        if not isinstance(survey, Mapping):
            raise _bad("key 'survey' must be a dict or None")
        hole = _array(_require(survey, "hole_index", "survey"), "survey['hole_index']", "i4", 1)
        at, azimuth, dip = (
            _array(_require(survey, k, "survey"), f"survey[{k!r}]", "f8", 1, len(hole))
            for k in ("depth", "azimuth", "dip")
        )
        for name, values in (("depth", at), ("azimuth", azimuth), ("dip", dip)):
            _finite(values, f"survey[{name!r}]")
        if len(hole) and (hole.min() < 0 or hole.max() >= len(holes)):
            raise _bad(f"survey['hole_index'] must lie in [0, {len(holes)})")
        if (np.diff(hole) < 0).any() or ((np.diff(hole) == 0) & (np.diff(at) <= 0)).any() or (at < 0).any():
            raise _bad("survey stations must be sorted by hole, with depth >= 0 and increasing within a hole")
        if ((azimuth < 0) | (azimuth >= 360)).any():
            raise _bad("survey['azimuth'] must lie in [0, 360)")
        if ((dip < -90) | (dip > 90)).any():
            raise _bad("survey['dip'] must lie in [-90, 90], negative downward")
        stations = (hole, at, azimuth, dip)
    tables = d.get("tables") or {}
    primary = _require(d, "intervals", "a drillholes")
    if primary is None and len(tables) == 1:
        (primary,) = tables.values()
        tables = {}
    dropped = sorted(tables) + (["collar columns"] if d["columns"] else [])
    if dropped:
        warnings.warn(
            f"boitatá Drillholes keep one interval table; dropped {dropped}", UserWarning, stacklevel=3
        )
    table = None
    if primary is not None:
        if not isinstance(primary, Mapping):
            raise _bad("key 'intervals' must be a dict or None")
        data, units = _intervals(primary, holes, "the intervals")
        table = _with_units(Table(data), units)
    return Drillholes._from_parts(
        holes, xyz, depths, offsets, stations, method, table, d["crs"], _label(d, "length_unit")
    )


def categories_from(obj: Any) -> Categories:
    """Categories from a protocol object of kind ``categories``.

    Raises
    ------
    InvalidInput
        When the dict breaks a key or category rule, naming it.
    """
    d = _open(obj, ("categories",), "Categories.from_minetypes")
    names = _entry("categories", d, "the protocol dict")
    return Categories(names, colors=d["colors"], mapping=dict(d["mapping"]), other=d["other"])


_FROM = {
    "table": table_from,
    "intervals": table_from,
    "categories": categories_from,
    "grid": blocks_from,
    "block_model": blocks_from,
    "point_set": points_from,
    "composites": points_from,
    "mesh": mesh_from,
    "polylines": polylines_from,
    "drillholes": drillholes_from,
}


def coerce(value: Any) -> Any:
    """``value`` as a boitatá container when it is a foreign protocol object of a kind boitatá holds."""
    if isinstance(value, (*OWN, type)):
        return value
    if isinstance(value, (list, tuple)) and any(_foreign(v) for v in value):
        return type(value)(coerce(v) for v in value)
    if not _foreign(value):
        return value
    spec = _as_spec(value)
    build = _FROM.get(spec.get("kind"))
    return value if build is None else build(spec)


def _foreign(value: Any) -> bool:
    return not isinstance(value, OWN) and callable(getattr(type(value), "__minetypes__", None))


def accepting(func: Any) -> Any:
    """``func`` taking any protocol object where it takes a container."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if any(_foreign(a) or isinstance(a, (list, tuple)) for a in args) or any(
            _foreign(v) or isinstance(v, (list, tuple)) for v in kwargs.values()
        ):
            args = tuple(coerce(a) for a in args)
            kwargs = {k: coerce(v) for k, v in kwargs.items()}
        return func(*args, **kwargs)

    wrapper.__minetypes_accepting__ = True
    return wrapper


def _wrap_class(cls: type) -> None:
    for name in list(vars(cls)):
        if name.startswith("_") or name in ("from_minetypes",):
            continue
        raw = inspect.getattr_static(cls, name)
        if isinstance(raw, staticmethod):
            setattr(cls, name, staticmethod(accepting(raw.__func__)))
        elif isinstance(raw, classmethod):
            setattr(cls, name, classmethod(accepting(raw.__func__)))
        elif (
            callable(raw) and not isinstance(raw, type) and not getattr(raw, "__minetypes_accepting__", False)
        ):
            try:
                setattr(cls, name, accepting(raw))
            except (AttributeError, TypeError):
                continue


_PRODUCERS = (
    (Table, table_minetypes, table_from),
    (PointSet, points_minetypes, points_from),
    (Polylines, polylines_minetypes, polylines_from),
    (Mesh, mesh_minetypes, mesh_from),
    (BlockModel, blocks_minetypes, blocks_from),
    (Drillholes, drillholes_minetypes, drillholes_from),
    (Categories, categories_minetypes, categories_from),
)


def install(namespace: dict[str, Any]) -> None:
    """Adds ``__minetypes__`` and ``from_minetypes`` to the containers, then makes every public
    function and method in ``namespace`` accept protocol objects."""
    for cls, produce, build in _PRODUCERS:
        produce.__name__ = produce.__qualname__ = "__minetypes__"
        produce.__qualname__ = f"{cls.__name__}.__minetypes__"
        cls.__minetypes__ = produce
        build.__qualname__ = f"{cls.__name__}.from_minetypes"
        cls.from_minetypes = staticmethod(build)
    for name, value in list(namespace.items()):
        if name.startswith("_") or inspect.ismodule(value):
            continue
        if isinstance(value, type):
            if value.__module__.startswith("boitata"):
                _wrap_class(value)
        elif callable(value) and getattr(value, "__module__", "") and value.__module__.startswith("boitata"):
            namespace[name] = accepting(value)
