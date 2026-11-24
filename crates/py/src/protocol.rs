use arrow_array::cast::AsArray;
use arrow_array::types::{Float32Type, Float64Type, Int32Type, Int64Type};
use arrow_array::{Array, ArrayRef, RecordBatch};
use arrow_schema::DataType;
use boitata_core::Layout;
use numpy::ndarray::{ArrayView1, ArrayView2};
use numpy::{Element, PyArray1, PyArray2};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::blocks::Mesh;
use crate::containers::{PyBlockModel, PyPointSet, PyPolylines};
use crate::drillholes::Drillholes;
use crate::invalid;
use crate::table::Table;

/// Keeps a record batch alive for the views into its buffers.
#[pyclass(module = "boitata", frozen)]
pub struct Keep(#[expect(dead_code, reason = "held only so the views stay valid")] pub RecordBatch);

fn read_only(array: Bound<'_, PyAny>) -> PyResult<Bound<'_, PyAny>> {
    let flags = PyDict::new(array.py());
    flags.set_item("write", false)?;
    array.call_method("setflags", (), Some(&flags))?;
    Ok(array)
}

/// A read-only view of `values`, which `owner` holds and never changes.
pub fn view1<'py, T: Element>(
    values: &[T],
    owner: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    // SAFETY: `owner` is a frozen object that owns `values` for as long as the array keeps it alive.
    let array = unsafe { PyArray1::borrow_from_array(&ArrayView1::from(values), owner.clone()) };
    read_only(array.into_any())
}

/// A read-only `(n, 3)` view of `rows`, which `owner` holds and never changes.
pub fn view3<'py, T: Element>(
    rows: &[[T; 3]],
    owner: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let flat = ArrayView2::from_shape((rows.len(), 3), rows.as_flattened()).expect("n x 3");
    // SAFETY: as in `view1`.
    let array = unsafe { PyArray2::borrow_from_array(&flat, owner.clone()) };
    read_only(array.into_any())
}

pub fn owned1<'py, T: Element>(py: Python<'py>, values: Vec<T>) -> PyResult<Bound<'py, PyAny>> {
    read_only(PyArray1::from_vec(py, values).into_any())
}

pub fn owned3<'py, T: Element + Copy>(
    py: Python<'py>,
    rows: &[[T; 3]],
) -> PyResult<Bound<'py, PyAny>> {
    let flat = ArrayView2::from_shape((rows.len(), 3), rows.as_flattened()).expect("n x 3");
    read_only(PyArray2::from_array(py, &flat).into_any())
}

fn finite<T: Into<f64> + Copy>(values: &[T], what: &str, name: &str) -> PyResult<()> {
    match values.iter().position(|v| (*v).into().is_infinite()) {
        Some(i) => Err(invalid(format!(
            "{what} column {name:?} holds infinity at row {i}; the protocol carries NaN for a missing value and no infinity"
        ))),
        None => Ok(()),
    }
}

fn nullable<T: Copy>(array: &dyn Array, values: &[T], missing: T) -> Vec<T> {
    values
        .iter()
        .enumerate()
        .map(|(i, v)| if array.is_null(i) { missing } else { *v })
        .collect()
}

fn category<'py>(py: Python<'py>, names: &[String]) -> PyResult<Bound<'py, PyDict>> {
    let entry = PyDict::new(py);
    entry.set_item("names", PyList::new(py, names)?)?;
    entry.set_item("colors", py.None())?;
    entry.set_item("mapping", PyDict::new(py))?;
    entry.set_item("other", py.None())?;
    Ok(entry)
}

/// The protocol array of one column, and its category names when it carries codes.
fn column<'py>(
    py: Python<'py>,
    array: &ArrayRef,
    owner: &Bound<'py, PyAny>,
    what: &str,
    name: &str,
) -> PyResult<(Bound<'py, PyAny>, Option<Vec<String>>)> {
    let nulls = array.null_count() > 0;
    let unsupported = |t: &DataType| {
        invalid(format!(
            "{what} column {name:?} has type {t}, which the protocol cannot carry; drop it or convert it to numbers or text first"
        ))
    };
    Ok(match array.data_type() {
        DataType::Float64 => {
            let v = array.as_primitive::<Float64Type>().values();
            finite(v, what, name)?;
            match nulls {
                true => (owned1(py, nullable(array.as_ref(), v, f64::NAN))?, None),
                false => (view1(v, owner)?, None),
            }
        }
        DataType::Float32 => {
            let v = array.as_primitive::<Float32Type>().values();
            finite(v, what, name)?;
            match nulls {
                true => (owned1(py, nullable(array.as_ref(), v, f32::NAN))?, None),
                false => (view1(v, owner)?, None),
            }
        }
        DataType::Int64 | DataType::Int32 if nulls => {
            let wide = arrow_cast::cast(array, &DataType::Float64).map_err(invalid)?;
            let v = wide.as_primitive::<Float64Type>().values();
            (owned1(py, nullable(wide.as_ref(), v, f64::NAN))?, None)
        }
        DataType::Int64 => (
            view1(array.as_primitive::<Int64Type>().values(), owner)?,
            None,
        ),
        DataType::Int32 => (
            view1(array.as_primitive::<Int32Type>().values(), owner)?,
            None,
        ),
        DataType::Int8
        | DataType::Int16
        | DataType::UInt8
        | DataType::UInt16
        | DataType::UInt32
        | DataType::UInt64 => {
            let options = arrow_cast::CastOptions {
                safe: false,
                ..Default::default()
            };
            let wide = arrow_cast::cast_with_options(array, &DataType::Int64, &options)
                .map_err(|e| invalid(format!("{what} column {name:?} does not fit int64: {e}")))?;
            return column(py, &wide, owner, what, name);
        }
        DataType::Boolean => {
            let b = array.as_boolean();
            match nulls {
                true => {
                    let codes = (0..b.len())
                        .map(|i| {
                            if b.is_null(i) {
                                -1
                            } else {
                                i32::from(b.value(i))
                            }
                        })
                        .collect();
                    (
                        owned1(py, codes)?,
                        Some(vec!["false".into(), "true".into()]),
                    )
                }
                false => (
                    owned1(py, (0..b.len()).map(|i| b.value(i)).collect())?,
                    None,
                ),
            }
        }
        DataType::Utf8 | DataType::LargeUtf8 | DataType::Utf8View | DataType::Dictionary(_, _) => {
            let text = arrow_cast::cast(array, &DataType::Utf8)
                .map_err(|_| unsupported(array.data_type()))?;
            let text = text.as_string::<i32>();
            if text.null_count() == 0 {
                let values: Vec<&str> = text.iter().map(|s| s.unwrap_or_default()).collect();
                let numpy = py.import("numpy")?;
                let kw = PyDict::new(py);
                kw.set_item("dtype", "str")?;
                let array = numpy.call_method("array", (PyList::new(py, values)?,), Some(&kw))?;
                (read_only(array)?, None)
            } else {
                let mut names: Vec<String> = text.iter().flatten().map(str::to_string).collect();
                names.sort();
                names.dedup();
                if names.first().is_some_and(String::is_empty) {
                    return Err(invalid(format!(
                        "{what} column {name:?} has missing text and an empty string; a category name is non-empty, so replace one of them"
                    )));
                }
                let codes = text
                    .iter()
                    .map(|s| match s {
                        Some(s) => names
                            .binary_search_by(|n| n.as_str().cmp(s))
                            .map_or(-1, |c| c as i32),
                        None => -1,
                    })
                    .collect();
                (owned1(py, codes)?, Some(names))
            }
        }
        other => return Err(unsupported(other)),
    })
}

/// `columns`, `units` and `categories` of `batch`, with `owner` keeping its buffers alive.
pub fn columns<'py>(
    py: Python<'py>,
    batch: &RecordBatch,
    owner: &Bound<'py, PyAny>,
    what: &str,
) -> PyResult<(Bound<'py, PyDict>, Bound<'py, PyDict>, Bound<'py, PyDict>)> {
    let (values, categories) = (PyDict::new(py), PyDict::new(py));
    for (field, array) in batch.schema().fields().iter().zip(batch.columns()) {
        let name = field.name();
        let (array, names) = column(py, array, owner, what, name)?;
        values.set_item(name, array)?;
        match names {
            Some(names) if names.is_empty() => {
                values.set_item(name, owned1(py, vec![f64::NAN; batch.num_rows()])?)?;
            }
            Some(names) => categories.set_item(name, category(py, &names)?)?,
            None => {}
        }
    }
    Ok((values, crate::table::units(py, batch)?, categories))
}

fn put<'py>(
    d: &Bound<'py, PyDict>,
    prefix: &str,
    parts: (Bound<'py, PyDict>, Bound<'py, PyDict>, Bound<'py, PyDict>),
) -> PyResult<()> {
    d.set_item(format!("{prefix}columns"), parts.0)?;
    d.set_item(format!("{prefix}units"), parts.1)?;
    d.set_item(format!("{prefix}categories"), parts.2)
}

/// The arrays of a boitata object for its `__minetypes__` dict.
#[pyfunction]
fn _minetypes_parts<'py>(obj: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyDict>> {
    let py = obj.py();
    let d = PyDict::new(py);
    if let Ok(t) = obj.cast::<Table>() {
        let batch = &t.get().0;
        put(&d, "", columns(py, batch, obj, "table")?)?;
        d.set_item("rows", batch.num_rows())?;
    } else if let Ok(p) = obj.cast::<PyPointSet>() {
        let p = &p.get().0;
        d.set_item("coords", view3(p.coords(), obj)?)?;
        put(&d, "", columns(py, p.attributes(), obj, "point set")?)?;
    } else if let Ok(l) = obj.cast::<PyPolylines>() {
        let l = &l.get().0;
        d.set_item("coords", view3(l.vertices(), obj)?)?;
        d.set_item("part_offsets", view1(l.part_offsets(), obj)?)?;
        d.set_item("feature_offsets", view1(l.feature_offsets(), obj)?)?;
        d.set_item("closed", view1(l.closed(), obj)?)?;
        put(&d, "", columns(py, l.attributes(), obj, "polylines")?)?;
    } else if let Ok(m) = obj.cast::<Mesh>() {
        let m = &m.get().mesh;
        d.set_item("coords", view3(m.vertices(), obj)?)?;
        d.set_item("triangles", view3(m.triangles(), obj)?)?;
        put(
            &d,
            "vertex_",
            columns(py, m.vertex_attributes(), obj, "mesh vertex")?,
        )?;
        put(
            &d,
            "face_",
            columns(py, m.face_attributes(), obj, "mesh face")?,
        )?;
    } else if let Ok(b) = obj.cast::<PyBlockModel>() {
        let b = &b.get().0;
        let g = b.geometry();
        d.set_item("origin", g.origin)?;
        d.set_item("size", g.size)?;
        d.set_item("count", g.count)?;
        d.set_item("rotation", g.rotation)?;
        let none = py.None();
        let (layout, index, parent, offset, scale, subgrid) = match b.layout() {
            Layout::Regular => (
                "regular",
                none.bind(py).clone(),
                none.bind(py).clone(),
                none.bind(py).clone(),
                none.bind(py).clone(),
                none.bind(py).clone(),
            ),
            Layout::Masked(i) => (
                "masked",
                view1(i, obj)?,
                none.bind(py).clone(),
                none.bind(py).clone(),
                none.bind(py).clone(),
                none.bind(py).clone(),
            ),
            Layout::SubBlocked {
                parent,
                extent,
                grid,
            } => {
                let centre: Vec<[f32; 3]> = extent
                    .iter()
                    .map(|e| [0, 1, 2].map(|k| ((e[k] + e[k + 3]) / 2.0) as f32))
                    .collect();
                let size: Vec<[f32; 3]> = extent
                    .iter()
                    .map(|e| [0, 1, 2].map(|k| (e[k + 3] - e[k]) as f32))
                    .collect();
                let subgrid = match grid {
                    Some(g) => PyList::new(py, g)?.into_any(),
                    None => none.bind(py).clone(),
                };
                (
                    "subblocked",
                    none.bind(py).clone(),
                    view1(parent, obj)?,
                    owned3(py, &centre)?,
                    owned3(py, &size)?,
                    subgrid,
                )
            }
        };
        d.set_item("layout", layout)?;
        d.set_item("index", index)?;
        d.set_item("parent", parent)?;
        d.set_item("offset", offset)?;
        d.set_item("scale", scale)?;
        d.set_item("subgrid", subgrid)?;
        put(&d, "", columns(py, b.attributes(), obj, "block model")?)?;
    } else if let Ok(h) = obj.cast::<Drillholes>() {
        h.get().minetypes_parts(py, &d)?;
    } else {
        return Err(invalid(format!(
            "{} has no protocol form",
            obj.get_type().name()?
        )));
    }
    Ok(d)
}

pub fn register(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<Keep>()?;
    m.add_function(wrap_pyfunction!(_minetypes_parts, m)?)?;
    Ok(())
}
