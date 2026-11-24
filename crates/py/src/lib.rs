use pyo3::prelude::*;
use pyo3::types::PyType;

mod args;
mod blocks;
mod categorical;
mod categories;
mod coda;
mod cokriging;
mod consistency;
mod containers;
mod drillholes;
mod eda;
mod estimation;
mod indicator;
mod io;
mod local_grid;
mod lva;
mod modeling;
mod multigaussian;
mod persist;
mod protocol;
mod simulation;
mod table;
mod transforms;
mod units;
mod variogram;

/// Raises `boitata.errors.<kind>`, a subclass of both `BoitataError` and a builtin.
pub(crate) fn error(kind: &str, message: impl ToString) -> PyErr {
    Python::attach(|py| {
        match py
            .import("boitata.errors")
            .and_then(|m| m.getattr(kind))
            .and_then(|c| Ok(c.cast_into::<PyType>()?))
        {
            Ok(class) => PyErr::from_type(class, message.to_string()),
            Err(e) => e,
        }
    })
}

/// Raises a `UserWarning` at the caller's line, past the frames of `boitata._protocol`'s wrapper.
pub(crate) fn warn(py: Python, message: String) -> PyResult<()> {
    let mut level = 1;
    let mut frame = py.import("sys")?.call_method1("_getframe", (0,))?;
    while !frame.is_none()
        && frame
            .getattr("f_globals")?
            .get_item("__name__")
            .and_then(|n| n.extract::<String>())
            .is_ok_and(|n| n == "boitata._protocol")
    {
        level += 1;
        frame = frame.getattr("f_back")?;
    }
    let category = py.get_type::<pyo3::exceptions::PyUserWarning>();
    PyErr::warn(py, &category, &std::ffi::CString::new(message)?, level)
}

pub(crate) fn invalid(message: impl ToString) -> PyErr {
    error("InvalidInput", message)
}

#[pymodule]
fn _boitata(m: &Bound<PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    table::register(m)?;
    m.add_class::<containers::PyPointSet>()?;
    m.add_class::<containers::PyPolylines>()?;
    m.add_class::<containers::PyBlockModel>()?;
    io::register(m)?;
    transforms::register(m)?;
    variogram::register(m)?;
    estimation::register(m)?;
    cokriging::register(m)?;
    indicator::register(m)?;
    drillholes::register(m)?;
    coda::register(m)?;
    blocks::register(m)?;
    m.add_class::<local_grid::LocalGrid>()?;
    lva::register(m)?;
    modeling::register(m)?;
    simulation::register(m)?;
    simulation::register_snesim(m)?;
    eda::register(m)?;
    categories::register(m)?;
    categorical::register(m)?;
    multigaussian::register(m)?;
    consistency::register(m)?;
    protocol::register(m)?;
    Ok(())
}
