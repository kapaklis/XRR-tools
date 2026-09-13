# XRR-tools

Tools for plotting and analyzing X-ray and neutron reflectometry output.

**GenX Figure Studio** turns GenX reflectometry / PNR exports into publication figures. It combines a modern HTML/CSS desktop interface with Python and Matplotlib, using **pywebview** as a lightweight Electron-like shell. It runs locally with native file dialogs; no Node build, external web service, or CDN is required.

## Current capabilities

- Dataset cards with visibility, editable legend labels, colors, markers, model line styles, and individual marker-size / line-width overrides. Empty size fields follow the figure defaults.
- Combined overlay, vertical column stack, or figure table with 1–4 columns. Separate panels follow dataset order; hidden datasets are omitted. Stacked panels share the Q axis.
- Large SVG preview with fit-to-view and zoom; text and strokes scale together at the final figure's aspect ratio.
- Grouped controls for layout, axes, typography, legend, and instrumental background.
- Single-column (3.35 in / 85.1 mm), double-column (7.2 in / 182.9 mm), and presentation presets, plus custom dimensions.
- Colorblind-friendly palette, open measurement markers, error bars, fine inward ticks, and optional major/minor grids.
- Serif/sans-serif typography, Matplotlib math notation, log/linear axes, and automatic or explicit limits.
- PDF with embedded TrueType fonts, SVG with editable text, and PNG at configurable resolution (600 DPI by default).
- Exact exported page dimensions; preview zoom does not change the output. PDF/SVG remain vector at any scale.
- Validation with visible error messages and disabled export while settings are invalid or preview is updating.

## Run from source

Requires **Python 3.10 or later**. On macOS, use a normal desktop Python installation (the OS-provided Python may be too old).

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -e .
python -m genx_figure_studio
```

On Windows:

```powershell
.venv\Scripts\activate
pip install -e .
python -m genx_figure_studio
```

The `genx-figure-studio` command is also installed. macOS uses WKWebView and Windows uses WebView2 (install Microsoft's WebView2 Runtime if missing). On Linux, install a supported desktop webview backend, for example `pip install 'pywebview[qt]>=5,<7'`, along with the Qt system libraries required by your distribution. A graphical desktop session is required; plotting and tests can run headlessly. See the [pywebview installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Figure workflow

1. Import `.dat`/`.txt` outputs from GenX.
2. Choose combined, column stack, or figure table under **Arrangement**, then a column-width preset. Dimensions apply to the whole exported figure; increase height for tall stacks or width for wide tables. Edit each dataset's labels and styles on the left. Channel labels retain condition names to distinguish datasets.
3. Set axis limits, typography, background cutoff, and legend placement. Empty limits use automatic scaling.
4. Choose PDF, SVG, or PNG in the **File format** dropdown in the Export section. Both export buttons show the chosen format; click either to open the native save dialog. DPI applies only to PNG. PNGs are limited to 40 megapixels; use vector output for larger figures.

Presets are starting points: match the destination journal's actual width and typography requirements. SVG text uses DejaVu fonts, so install those fonts in your illustration editor to preserve its appearance; PDF embeds them. Review long titles and legends at final print size before submission.

## GenX input format

The GUI expects GenX text exports with columns equivalent to:

```text
Qz    I_simulated    I_measured    error(I)
```

Dataset names in GenX headers are used when available. Three-column files are supported without uncertainties. Rows are sorted by Q; rows with nonfinite Q are omitted and reported. Negative uncertainties are rejected. Nonfinite measurements, nonpositive measurements on logarithmic axes, and measurements below an enabled cutoff are omitted from the plot and reported. Missing uncertainties do not remove the corresponding measured points.

The default cutoff is `1e-6`: on log axes, points below it are hidden and the model is clipped to it. Both operations can be disabled independently; source arrays and files are preserved. The preview uses the same figure builder and physical dimensions as export.

## Development and verification

```bash
pip install -e . pytest
python -m pytest -q
node --check src/genx_figure_studio/ui/app.js  # optional JS syntax check
node tests/test_export_format.cjs            # export-selector regression check
```

Tests cover parsing, uncertainty handling, masking, settings validation, exact PNG/SVG/PDF dimensions, embedded PDF fonts, native-dialog cancellation, and preservation of existing files if export fails. UI assets ship as Python package data. The plotting core lives in `plotting.py`, the native bridge in `app.py`, and the interface in `ui/`.

## Development priorities

1. broader GenX header/channel formats;
2. persistent project/settings files;
3. residual and spin-asymmetry panels;
4. configurable vertical offsets;
5. journal-style presets;
6. 2x2 PNR-panel figure mode;
7. improved legend composition;
8. tests for file parsing and plotting state.

## Magnetization editor

Run `python magnetization_profile.py` to open the editor with the fitted angles and moments stored in that script. To start with an empty editor, run `python -m genx_figure_studio.magnetization_app` (or `genx-magnetization-studio` after reinstalling the package).

Paste angle values in degrees, a comma-separated list, or GenX parameter rows containing `magn_ang`. For other multi-column tables, explicitly select the angle column. Choose whether input runs from substrate to surface or the reverse. Optional moments accept a shared magnitude or one value per angle; blank means equal-length direction arrows. The parsed-values panel lets you verify the mapping before export.

The live vector preview uses a translucent Fe/MgO stack inspired by Figure 3 of [Phys. Rev. B 97, 174424](https://doi.org/10.1103/PhysRevB.97.174424). Controls cover titles, custom layer labels, colors, fonts, arrow sizes, field direction, visibility, projection, figure dimensions, and footnotes. Layers are schematic; thickness values appear in the editable note. Fe1 remains substrate-adjacent, with angles measured counterclockwise from +x in the film plane. Projection foreshortens arrows; supplied magnitudes are displayed without unit conversion.

Choose PDF, SVG, or PNG in the editor before opening the native save dialog. PDF embeds fonts; SVG preserves editable text. Settings apply to preview and export, and invalid inputs disable export. Edits last for the current session; exports do not modify the input script. `python magnetization_profile.py --plot` retains the direct plotting workflow. The reusable plotting function is `genx_figure_studio.magnetization.plot_genx_magnetization`.
