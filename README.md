# XRR-tools

Tools for plotting and analyzing X-ray and neutron reflectometry output.

The repository currently contains **GenX Figure Studio**, a Python/Tkinter application for turning GenX exported reflectometry / PNR `.dat` files into manuscript-ready figures.

## Current capabilities

- Load multiple GenX exported data files.
- Plot selected datasets on one shared figure.
- Display measured points with optional error bars and GenX simulated curves.
- Logarithmic or linear reflectivity axis.
- Configurable instrumental background cutoff (default `1e-6`).
- Editable labels, colors, markers, line styles and axis limits.
- Stable interactive preview independent of export dimensions.
- Optional major/minor grid.
- Export to PDF, SVG and high-resolution PNG.
- Single-column, double-column and presentation-size presets.

## Run from source

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
pip install -e .
python -m genx_figure_studio
```

On Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python -m genx_figure_studio
```

## GenX input format

The GUI expects GenX text exports with columns equivalent to:

```text
Qz    I_simulated    I_measured    error(I)
```

Dataset names in GenX headers are used when available.

## Development priorities

1. robust GenX header/channel parser;
2. persistent project/settings files;
3. residual and spin-asymmetry panels;
4. configurable vertical offsets;
5. journal-style presets;
6. 2x2 PNR-panel figure mode;
7. improved legend composition;
8. tests for file parsing and plotting state.
