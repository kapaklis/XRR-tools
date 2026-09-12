"""Checks for scientific data handling and export fidelity. Run with pytest."""
from io import BytesIO
import re
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import matplotlib as mpl
import numpy as np
from PIL import Image
import pytest

from genx_figure_studio.app import StudioAPI
from genx_figure_studio.plotting import PRESETS, build_figure, read_genx_dat, render_figure, validate_settings


def _data():
    return dict(name="test export", path="test.dat", channel="", condition="",
                q=np.array([.01, .02, .03]), sim=np.array([1., .1, .01]),
                obs=np.array([.99, .11, .011]), err=np.array([.01, .01, .001]))


def test_parser_sorts_preserves_channel_and_handles_missing_errors(tmp_path):
    path = tmp_path / "example.dat"
    path.write_text('\ufeff\n  # Dataset "00_300K"\n0.2 0.1 0.11\n0.1 0.2 0.21\nnan 1 1\n')
    data = read_genx_dat(path)
    assert data["channel"] == "00" and data["condition"] == "300K"
    np.testing.assert_equal(data["q"], [.1, .2])
    np.testing.assert_equal(data["obs"], [.21, .11])
    assert data["err"] is None and data["skipped"] == 1
    path.write_text("0.1 0.2 0.3 0.01\n")
    assert read_genx_dat(path)["q"].shape == (1,)
    path.write_text("0.1 0.2 0.3 -0.01\n")
    with pytest.raises(ValueError, match="nonnegative"):
        read_genx_dat(path)
    path.write_text("0.1 0.2\n")
    with pytest.raises(ValueError, match="Expected Q"):
        read_genx_dat(path)


def test_log_mask_does_not_lose_points_with_missing_uncertainties():
    data = dict(name="test", q=np.arange(5.), obs=np.array([1., .1, -1., 1e-8, np.nan]),
                sim=np.array([1., .1, 1e-8, np.nan, .01]), err=np.array([.1, np.nan, 0., 0., 0.]))
    original = data["sim"].copy()
    figure, notes = build_figure([data], validate_settings({}))
    np.testing.assert_equal(figure.axes[0].lines[0].get_ydata(), [1., .1])
    np.testing.assert_equal(figure.axes[0].lines[1].get_ydata(), [1., .1, 1e-6, np.nan, .01])
    np.testing.assert_equal(data["sim"], original)
    assert any("3 measured points omitted" in note for note in notes)
    assert any("uncertainties omitted" in note for note in notes)
    figure, _ = build_figure([data], validate_settings(dict(scale="linear", ymin="", ymax="")))
    assert len(figure.axes[0].lines[0].get_ydata()) == 4


@pytest.mark.parametrize("settings", [dict(width=0), dict(dpi="oops"), dict(dpi=72.5),
    dict(xmin=2, xmax=1), dict(ymin=0), dict(fontsize="nan"), dict(scale="invalid"), dict(background=-1)])
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        validate_settings(settings)


def test_exports_have_exact_dimensions_fonts_and_no_global_style_changes():
    api = StudioAPI()
    rows = [api._register(_data())]
    data = api._resolve(rows)
    before = mpl.rcParams.copy()
    settings = {**PRESETS["single"], "dpi": 100}
    svg, _ = render_figure(data, settings)
    root = ET.fromstring(svg)
    assert root.attrib["width"] == "241.2pt"
    assert root.attrib["height"] == "198pt"
    assert "<text" in svg.decode()  # Editable exported text.
    preview, _ = render_figure(data, settings, preview=True)
    assert "<text" not in preview.decode()  # Portable preview without font substitution.
    pdf, _ = render_figure(data, settings, "pdf")
    assert pdf.startswith(b"%PDF")
    assert re.search(rb"/MediaBox\s*\[\s*0\s+0\s+241.2\s+198\s*\]", pdf)
    assert b"/FontFile2" in pdf  # Embedded TrueType font, not Type 3 glyphs.
    png, _ = render_figure(data, settings, "png")
    image = Image.open(BytesIO(png))
    assert image.size == (335, 275)
    assert image.getpixel((0, 0)) == (255, 255, 255, 255)
    assert mpl.rcParams["font.size"] == before["font.size"]
    assert mpl.rcParams["svg.fonttype"] == before["svg.fonttype"]
    with pytest.raises(ValueError, match="40 megapixels"):
        render_figure(data, dict(width=20, height=20, dpi=1200), "png")
    with pytest.raises(ValueError, match="Select at least one"):
        render_figure([{**d, "visible": False} for d in data], {})


def test_native_import_export_cancel_and_error_paths(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1, SAVE=2)))
    api = StudioAPI()
    good, bad = tmp_path / "good.dat", tmp_path / "bad.dat"
    good.write_text("0.01 1 0.99 0.01\n0.02 0.1 0.11 0.01\n")
    bad.write_text("not data\n")
    api._window = SimpleNamespace(create_file_dialog=lambda *a, **k: (str(good), str(bad)))
    result = api.load_files()
    assert len(result["datasets"]) == 1 and len(result["errors"]) == 1
    rows = result["datasets"]
    assert api.preview(rows, {})["image"].startswith("data:image/svg+xml;base64,")
    assert "error" in api.preview(rows, dict(ymin=-1))
    destination = tmp_path / "figure.pdf"
    api._window.create_file_dialog = lambda *a, **k: (str(destination),)
    assert api.export(rows, {}, "pdf")["path"] == str(destination)
    assert destination.read_bytes().startswith(b"%PDF")
    api._window.create_file_dialog = lambda *a, **k: None
    assert api.export(rows, {}, "svg")["cancelled"]
    api._window.create_file_dialog = lambda *a, **k: (str(tmp_path / "figure"),)
    api._window.create_confirmation_dialog = lambda *a: False
    assert api.export(rows, {}, "pdf")["cancelled"]
    destination.write_bytes(b"previous figure")
    api._window.create_file_dialog = lambda *a, **k: (str(destination),)
    monkeypatch.setattr("genx_figure_studio.app.os.replace", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    assert "disk full" in api.export(rows, {}, "pdf")["error"]
    assert destination.read_bytes() == b"previous figure"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.dat", "figure.pdf", "good.dat"]
    api.remove_dataset(rows[0]["id"])
    assert "error" in api.preview(rows, {})


@pytest.mark.parametrize("arrangement, columns, expected", [("overlay", 2, 1), ("stack", 2, 3), ("table", 2, 3)])
def test_panel_layouts_and_individual_style_sizes(arrangement, columns, expected):
    data = [{**_data(), "label": f"Dataset {i}", "markersize": str(i + 2), "linewidth": str(i + 1)} for i in range(3)]
    data.append({**_data(), "visible": False})
    settings = validate_settings(dict(arrangement=arrangement, panelcols=columns, height=8))
    figure, _ = build_figure(data, settings)
    assert len(figure.axes) == expected
    for i in range(3):
        ax = figure.axes[0 if arrangement == "overlay" else i]
        start = 2 * i if arrangement == "overlay" else 0
        assert ax.lines[start].get_markersize() == i + 2
        assert ax.lines[start + 1].get_linewidth() == i + 1
        if arrangement != "overlay":
            assert ax.get_title(loc="left") == f"({i + 1}) Dataset {i}"
    if arrangement == "stack":
        assert figure.axes[0].get_shared_x_axes().joined(figure.axes[0], figure.axes[2])
        assert figure.axes[0].get_xlabel() == ""
        assert figure.axes[2].get_xlabel()
    if arrangement == "table":
        assert figure.axes[2].get_subplotspec().rowspan.start == 1
        assert figure.axes[1].get_subplotspec().colspan.start == 1
    assert render_figure(data, settings, "pdf")[0].startswith(b"%PDF")
    data[0]["markersize"] = ""
    fallback, _ = build_figure(data, settings)
    assert fallback.axes[0].lines[0].get_markersize() == settings["markersize"]
    data[0]["linewidth"] = -1
    with pytest.raises(ValueError, match="linewidth must be between"):
        build_figure(data, settings)
