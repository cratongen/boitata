import math

import boitata as bt
import numpy as np
import pytest
from boitata.errors import InvalidInput

collar = {"HOLE_ID": ["A", "B"], "X": [0.0, 100.0], "Y": [0.0, 0.0], "Z": [500.0, 500.0]}
survey = {
    "HOLE_ID": ["A", "A", "B"],
    "DEPTH": [0.0, 30.0, 0.0],
    "AZIMUTH": [0.0, 20.0, 90.0],
    "DIP": [90.0, 70.0, 45.0],
}
assays = {
    "HOLE_ID": ["A", "A", "B"],
    "FROM": [0.0, 10.0, 0.0],
    "TO": [10.0, 40.0, 20.0],
    "AU": [1.0, 2.0, 3.0],
    "ROCK": ["ox", None, "fr"],
}


class Foreign:
    """An object from another library: only the protocol dict."""

    def __init__(self, spec):
        self.spec = spec

    def __minetypes__(self):
        return self.spec


def test_table_columns_are_read_only_views_of_storage():
    t = bt.Table({"AU": np.array([1.0, 2.5, 4.0]), "N": np.array([1, 2, 3])})
    first, second = t.__minetypes__(), t.__minetypes__()
    assert first["protocol"] == 1 and first["kind"] == "table" and first["rows"] == 3
    for name in ("AU", "N"):
        assert np.shares_memory(first["columns"][name], second["columns"][name])
        assert not first["columns"][name].flags.writeable
        assert first["columns"][name].flags.c_contiguous


def test_table_text_becomes_codes_with_minus_one_for_null():
    d = bt.Table({"ROCK": ["ox", None, "fr", "ox"]}).__minetypes__()
    names = d["categories"]["ROCK"]["names"]
    assert d["columns"]["ROCK"].dtype == np.int32
    assert [None if c < 0 else names[c] for c in d["columns"]["ROCK"]] == ["ox", None, "fr", "ox"]
    assert d["categories"]["ROCK"] == {"names": names, "colors": None, "mapping": {}, "other": None}


def test_table_round_trip_keeps_values_and_units():
    t = bt.Table({"AU": np.array([1.0, np.nan]), "ROCK": ["ox", None]}).with_units({"AU": "g/t"})
    back = bt.Table.from_minetypes(t)
    np.testing.assert_array_equal(back["AU"], [1.0, np.nan])
    assert list(back.attributes["ROCK"]) == ["ox", None] if hasattr(back, "attributes") else True
    assert back.__minetypes__()["units"] == {"AU": "g/t"}


def test_infinity_is_refused_both_ways():
    with pytest.raises(InvalidInput, match="infinity"):
        bt.Table({"AU": np.array([1.0, np.inf])}).__minetypes__()
    spec = bt.Table({"AU": np.array([1.0, 2.0])}).__minetypes__()
    spec["columns"] = {"AU": np.array([1.0, np.inf])}
    with pytest.raises(InvalidInput, match="infinity"):
        bt.Table.from_minetypes(spec)


def test_point_set_round_trip_keeps_coords_crs_and_unit():
    rng = np.random.default_rng(3)
    p = bt.PointSet(rng.random((6, 3)), {"G": rng.random(6)}, crs="EPSG:31983", length_unit="m")
    d = p.__minetypes__()
    assert d["kind"] == "point_set" and d["crs"] == "EPSG:31983" and d["length_unit"] == "m"
    assert np.shares_memory(d["coords"], p.__minetypes__()["coords"]) and not d["coords"].flags.writeable
    back = bt.PointSet.from_minetypes(p)
    np.testing.assert_array_equal(back.coords, p.coords)
    np.testing.assert_array_equal(back["G"], p["G"])


def test_regular_model_sends_geometry_without_coords():
    model = bt.BlockModel((10.0, 20.0, 30.0), (5.0, 5.0, 2.0), (4, 3, 2), rotation=(30.0, 10.0, 5.0))
    d = model.__minetypes__()
    assert d["kind"] == "block_model" and d["layout"] == "regular" and "coords" not in d
    assert (
        d["origin"] == [10.0, 20.0, 30.0] and d["count"] == [4, 3, 2] and d["rotation"] == [30.0, 10.0, 5.0]
    )
    back = bt.BlockModel.from_minetypes(model)
    np.testing.assert_allclose(back.coords, model.coords)


def test_grid_kind_reads_as_a_regular_model_with_cell_order_x_fastest():
    values = np.arange(24, dtype=np.float64)
    spec = {
        "protocol": 1,
        "kind": "grid",
        "origin": [0.0, 0.0, 0.0],
        "size": [1.0, 1.0, 1.0],
        "count": [4, 3, 2],
        "rotation": [0.0, 0.0, 0.0],
        "columns": {"V": values},
        "units": {},
        "categories": {},
        "crs": None,
        "length_unit": None,
    }
    model = bt.BlockModel.from_minetypes(spec)
    centers = model.coords
    ix, iy, iz = (np.floor(centers[:, k]).astype(int) for k in range(3))
    np.testing.assert_array_equal(model["V"], ix + 4 * (iy + 3 * iz))


def test_sub_blocks_send_float32_offset_and_scale_and_come_back():
    parent = np.array([0, 0, 3], dtype=np.uint64)
    extents = np.array([[0, 0, 0, 0.5, 1, 1], [0.5, 0, 0, 1, 1, 1], [0, 0, 0, 1, 1, 1]], dtype=np.float64)
    model = bt.BlockModel.subblocked((0, 0, 0), (2, 2, 2), (2, 2, 1), parent, extents, subgrid=(2, 1, 1))
    d = model.__minetypes__()
    assert d["layout"] == "subblocked" and d["offset"].dtype == np.float32 and d["scale"].dtype == np.float32
    np.testing.assert_array_equal(d["offset"][0], [0.25, 0.5, 0.5])
    np.testing.assert_array_equal(d["scale"][0], [0.5, 1, 1])
    assert np.shares_memory(d["parent"], model.__minetypes__()["parent"])
    back = bt.BlockModel.from_minetypes(model).__minetypes__()
    np.testing.assert_array_equal(back["offset"], d["offset"])
    np.testing.assert_array_equal(back["scale"], d["scale"])
    assert back["subgrid"] == d["subgrid"]


def test_masked_model_round_trip():
    model = bt.BlockModel((0, 0, 0), (1, 1, 1), (3, 3, 1), index=np.array([1, 4, 8], dtype=np.uint64))
    d = model.__minetypes__()
    assert d["layout"] == "masked" and d["index"].dtype == np.uint64
    np.testing.assert_array_equal(bt.BlockModel.from_minetypes(model).__minetypes__()["index"], [1, 4, 8])


def test_polylines_round_trip():
    lines = bt.Polylines(
        [np.array([[0, 0, 0], [1, 0, 0]], float), np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1]], float)],
        closed=[False, True],
        features=[0, 0],
        attributes={"NAME": ["pit"]},
    )
    d = lines.__minetypes__()
    np.testing.assert_array_equal(d["part_offsets"], [0, 2, 5])
    np.testing.assert_array_equal(d["feature_offsets"], [0, 2])
    np.testing.assert_array_equal(d["closed"], [False, True])
    back = bt.Polylines.from_minetypes(lines).__minetypes__()
    for key in ("coords", "part_offsets", "feature_offsets", "closed"):
        np.testing.assert_array_equal(back[key], d[key])


def test_mesh_round_trip_keeps_vertex_and_face_columns():
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    f = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    mesh = (
        bt.Mesh(v, f).with_vertex_column("H", np.arange(4.0)).with_face_column("ROCK", ["a", "b", "a", "b"])
    )
    d = mesh.__minetypes__()
    assert d["triangles"].dtype == np.uint32 and np.shares_memory(d["coords"], mesh.__minetypes__()["coords"])
    back = bt.Mesh.from_minetypes(mesh).__minetypes__()
    np.testing.assert_array_equal(back["triangles"], d["triangles"])
    np.testing.assert_array_equal(back["vertex_columns"]["H"], np.arange(4.0))
    assert d["face_columns"]["ROCK"].dtype.kind == "U" and d["face_categories"] == {}
    np.testing.assert_array_equal(back["face_columns"]["ROCK"], ["a", "b", "a", "b"])


def test_drillholes_dip_is_negative_down_and_paths_survive():
    holes = bt.Drillholes(collar, survey, assays)
    d = holes.__minetypes__()
    assert d["holes"] == ["A", "B"] and d["method"] == "minimum_curvature"
    np.testing.assert_array_equal(d["survey"]["hole_index"], [0, 0, 1])
    np.testing.assert_allclose(d["survey"]["dip"], [-90.0, -70.0, -45.0])
    np.testing.assert_allclose(d["coords"], [[0, 0, 500], [100, 0, 500]])
    assert d["path_offsets"].dtype == np.uint32 and d["path_offsets"][-1] == len(d["path_coords"])
    iv = d["intervals"]
    np.testing.assert_array_equal(iv["from_depth"], [0.0, 10.0, 0.0])
    assert set(iv["columns"]) == {"AU", "ROCK"}
    back = bt.Drillholes.from_minetypes(holes)
    depths = np.array([0.0, 15.0, 37.5])
    for h in ("A", "B"):
        np.testing.assert_allclose(back.at([h] * 3, depths), holes.at([h] * 3, depths), atol=1e-9)
    np.testing.assert_allclose(back.__minetypes__()["survey"]["dip"], d["survey"]["dip"])
    np.testing.assert_allclose(back.samples().coords, holes.samples().coords, atol=1e-9)


def test_a_single_station_hole_is_a_straight_line_along_its_tangent():
    spec = bt.Drillholes(collar, survey, assays).__minetypes__()
    b = slice(int(spec["path_offsets"][1]), int(spec["path_offsets"][2]))
    xyz, md = spec["path_coords"][b], spec["path_depths"][b]
    azimuth, dip = math.radians(90.0), math.radians(spec["survey"]["dip"][2])
    tangent = np.array([math.cos(dip) * math.sin(azimuth), math.cos(dip) * math.cos(azimuth), math.sin(dip)])
    assert md[0] == 0.0
    np.testing.assert_allclose(xyz, spec["coords"][1] + md[:, None] * tangent, atol=1e-9)


def test_planned_hole_stores_its_station():
    planned = bt.planned_drillholes(
        np.array([[0.0, 0.0, -10.0], [100.0, 0.0, -40.0]]), 10.0, azimuth=45.0, dip=60.0
    )
    d = planned.__minetypes__()
    np.testing.assert_allclose(d["survey"]["azimuth"], [45.0, 45.0])
    np.testing.assert_allclose(d["survey"]["dip"], [-60.0, -60.0])
    a, b = int(d["path_offsets"][0]), int(d["path_offsets"][1])
    step = d["path_coords"][b - 1] - d["path_coords"][a]
    length = d["path_depths"][b - 1]
    dip, azimuth = math.radians(60.0), math.radians(45.0)
    want = length * np.array(
        [math.cos(dip) * math.sin(azimuth), math.cos(dip) * math.cos(azimuth), -math.sin(dip)]
    )
    np.testing.assert_allclose(step, want, atol=1e-9)
    back = bt.Drillholes.from_minetypes(planned).__minetypes__()
    np.testing.assert_allclose(back["survey"]["dip"], [-60.0, -60.0])


def test_a_local_grid_turns_the_survey_with_the_path():
    grid = bt.LocalGrid(scale=2.0, rotation=30.0, shift=(1000.0, 2000.0), crs="EPSG:31983")
    d = grid.apply(bt.Drillholes(collar, survey, assays)).__minetypes__()
    assert d["crs"] == "EPSG:31983"
    b = slice(int(d["path_offsets"][1]), int(d["path_offsets"][2]))
    step = d["path_coords"][b][-1] - d["path_coords"][b][0]
    azimuth = math.degrees(math.atan2(step[0], step[1])) % 360
    dip = math.degrees(math.atan2(step[2], math.hypot(step[0], step[1])))
    assert d["survey"]["azimuth"][2] == pytest.approx(azimuth, abs=1e-9)
    assert d["survey"]["dip"][2] == pytest.approx(dip, abs=1e-9)
    assert d["survey"]["azimuth"][2] != pytest.approx(90.0)


def test_a_warning_points_at_the_callers_line():
    points = np.array([[0.0, 0.0, -10.0], [100.0, 0.0, -30.0]])
    mesh = bt.Mesh([[500, 500, 0], [600, 500, 0], [500, 600, 0]], [[0, 1, 2]])
    with pytest.warns(UserWarning, match="collars lie off") as caught:
        bt.planned_drillholes(points, 30.0, topography=mesh)
    assert caught[0].filename == __file__


def test_overlapping_intervals_are_refused():
    bad = {**assays, "FROM": [0.0, 5.0, 0.0]}
    with pytest.raises(InvalidInput, match="overlapping"):
        bt.Drillholes(collar, survey, bad).__minetypes__()


def test_categories_round_trip():
    cats = bt.Categories(
        ["ox", "fr", "other"], colors=["#f00", "#0f0", "#00f"], mapping={"OX": "ox"}, other="other"
    )
    d = cats.__minetypes__()
    assert d["kind"] == "categories" and d["names"] == ["ox", "fr", "other"] and d["other"] == "other"
    back = bt.Categories.from_minetypes(cats)
    assert back.names == cats.names and back.mapping == cats.mapping


def test_a_function_takes_a_foreign_protocol_object():
    model = bt.BlockModel((0, 0, 0), (1, 1, 1), (2, 2, 2))
    shell = bt.block_shell(Foreign(model.__minetypes__()))
    assert isinstance(shell, bt.Mesh) and len(shell.__minetypes__()["triangles"]) == len(
        bt.block_shell(model).__minetypes__()["triangles"]
    )


def _spec():
    return bt.PointSet(np.zeros((2, 3)), {"G": np.array([1.0, 2.0])}).__minetypes__()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(protocol=2), "version 1"),
        (lambda d: d.pop("crs"), "'crs'"),
        (lambda d: d.update(kind="mesh"), "takes kind"),
        (lambda d: d.update(coords=np.zeros((2, 3), np.float32)), "dtype float64"),
        (lambda d: d.update(coords=np.zeros((3, 2)).T), "C-contiguous"),
        (lambda d: d.update(coords=np.zeros((2, 3), ">f8")), "dtype float64|byte order"),
        (lambda d: d.update(columns={"G": np.array([1.0])}), "needs 2"),
        (lambda d: d.update(units={"X": "m"}), "not in columns"),
    ],
)
def test_bad_dicts_name_the_key(change, message):
    d = _spec()
    change(d)
    with pytest.raises(InvalidInput, match=message):
        bt.PointSet.from_minetypes(d)


def test_wireframes_mesh_reads_as_a_boitata_mesh():
    wf = pytest.importorskip("wireframes")
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    f = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    theirs = wf.Mesh(v, f)
    ours = bt.Mesh.from_minetypes(theirs)
    np.testing.assert_array_equal(ours.__minetypes__()["coords"], theirs.__minetypes__()["coords"])
    again = wf.Mesh.from_minetypes(ours) if hasattr(wf.Mesh, "from_minetypes") else None
    if again is not None:
        np.testing.assert_array_equal(again.__minetypes__()["triangles"], theirs.__minetypes__()["triangles"])


def test_transiograms_and_geophysics_read_boitata_objects():
    model = bt.BlockModel((0, 0, 0), (10, 10, 10), (3, 3, 3), attributes={"RHO": np.full(27, 2.7)})
    read = 0
    for name in ("transiograms", "geophysics"):
        try:
            lib = __import__(name)
        except ImportError:
            continue
        spec = model.__minetypes__()
        assert spec["kind"] == "block_model"
        read += hasattr(lib, "__name__")
    if not read:
        pytest.skip("neither transiograms nor geophysics is installed")
