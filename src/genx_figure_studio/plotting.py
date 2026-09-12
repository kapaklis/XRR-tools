"""GenX input and publication figures, independent of the desktop shell."""
from io import BytesIO
from pathlib import Path
import re
import threading

import matplotlib as mpl
from matplotlib.figure import Figure
import numpy as np

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
LABELS = {"00": r"$R^{++}$", "11": r"$R^{--}$", "01": r"$R^{+-}$", "10": r"$R^{-+}$"}
PRESETS = {
    "single": dict(width=3.35, height=2.75, fontsize=8, markersize=2.7, linewidth=1.1, legendcols=1),
    "double": dict(width=7.2, height=4.8, fontsize=9, markersize=3.2, linewidth=1.4, legendcols=2),
    "presentation": dict(width=10, height=6.5, fontsize=12, markersize=4.5, linewidth=2, legendcols=2),
}
DEFAULTS = dict(
    **PRESETS["double"], scale="log", title="", xlabel=r"$Q_z$ ($\AA^{-1}$)",
    ylabel="Reflectivity", xmin="", xmax="", ymin="1e-7", ymax="1",
    background=1e-6, dpi=600, errors=True, legend=True, grid=False,
    mask=True, clip=True, font="sans-serif", legendloc="best", arrangement="overlay", panelcols=2,
)
# Matplotlib's rc context is process-global; pywebview invokes API calls on threads.
PLOT_LOCK = threading.Lock()


def read_genx_dat(path):
    path = Path(path)
    name = path.stem
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            if not line.lstrip().startswith("#"):
                break
            match = re.search(r'Dataset\s+"([^"]+)"', line)
            if match:
                name = match.group(1)
    values = np.loadtxt(path, comments="#", ndmin=2, encoding="utf-8-sig")
    if not values.size or values.shape[1] < 3:
        raise ValueError("Expected Q, simulated intensity, measured intensity, and optional uncertainty columns.")
    valid_q = np.isfinite(values[:, 0])
    if not valid_q.any():
        raise ValueError("No finite Q values were found.")
    skipped = int((~valid_q).sum())
    values = values[valid_q]
    values = values[np.argsort(values[:, 0], kind="stable")]
    if not np.isfinite(values[:, 1:3]).any():
        raise ValueError("No finite simulated or measured intensities were found.")
    if values.shape[1] > 3 and (values[:, 3] < 0).any():
        raise ValueError("Uncertainties must be nonnegative. Check the column order.")
    parts = name.split("_")
    channel = parts[0] if parts[0] in LABELS else ""
    return dict(path=str(path.resolve()), name=name, channel=channel,
                condition=" ".join(parts[1:]), q=values[:, 0], sim=values[:, 1],
                obs=values[:, 2], err=values[:, 3] if values.shape[1] > 3 else None,
                skipped=skipped)


def validate_settings(settings):
    result = {**DEFAULTS, **settings}
    bounds = dict(width=(1.5, 20), height=(1.5, 20), fontsize=(5, 32),
                  markersize=(0.5, 15), linewidth=(0.2, 8), legendcols=(1, 6),
                  dpi=(72, 1200), background=(1e-20, 1e10), panelcols=(1, 4))
    for key, (low, high) in bounds.items():
        try:
            value = float(result[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key.capitalize()} must be a number.") from None
        if not np.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key.capitalize()} must be between {low:g} and {high:g}.")
        if key in ("legendcols", "dpi", "panelcols") and not value.is_integer():
            raise ValueError(f"{key.capitalize()} must be a whole number.")
        result[key] = int(value) if key in ("legendcols", "dpi", "panelcols") else value
    for key in ("xmin", "xmax", "ymin", "ymax"):
        value = result[key]
        if value is None or str(value).strip() == "":
            result[key] = None
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number or empty for automatic limits.") from None
        if not np.isfinite(value):
            raise ValueError(f"{key} must be finite.")
        if key.startswith("y") and result["scale"] == "log" and value <= 0:
            raise ValueError("Logarithmic Y limits must be positive.")
        result[key] = value
    for axis in ("x", "y"):
        low, high = result[axis + "min"], result[axis + "max"]
        if low is not None and high is not None and low >= high:
            raise ValueError(f"{axis.upper()} minimum must be smaller than its maximum.")
    for key, choices in dict(scale=("log", "linear"), font=("sans-serif", "serif"),
                             arrangement=("overlay", "stack", "table"),
                             legendloc=("best", "upper right", "upper left", "lower left", "lower right")).items():
        if result[key] not in choices:
            raise ValueError(f"Unsupported {key}.")
    return result


def build_figure(datasets, settings):
    """Build at final print size. Called inside render_figure's rc context."""
    s = settings
    fig = Figure(figsize=(s["width"], s["height"]), layout="constrained", facecolor="white")
    visible = [d for d in datasets if d.get("visible", True)]
    if not visible:
        raise ValueError("Select at least one dataset to preview or export.")
    log = s["scale"] == "log"
    notes = []
    separate = s["arrangement"] != "overlay"
    columns = min(s["panelcols"], len(visible)) if s["arrangement"] == "table" else 1
    count = len(visible) if separate else 1
    panel_rows = (count + columns - 1) // columns
    axes = fig.subplots(panel_rows, columns, squeeze=False,
                        sharex=s["arrangement"] == "stack").ravel()
    for unused in axes[count:]:
        fig.delaxes(unused)
    axes = axes[:count]
    if separate and (s["height"] / panel_rows < 1.6 or s["width"] / columns < 2):
        notes.append("Panels are compact. Increase the total figure width or height for legible print output.")
    for index, d in enumerate(visible):
        ax = axes[index] if separate else axes[0]
        q, obs, sim = d["q"], d["obs"], d["sim"].copy()
        selected = np.isfinite(obs)
        if log:
            selected &= obs > 0
            if s["mask"]:
                selected &= obs >= s["background"]
        color = d.get("color", COLORS[0])
        if not mpl.colors.is_color_like(color):
            raise ValueError("Choose a valid dataset color.")
        marker, line = d.get("marker", "o"), d.get("line", "-")
        if marker not in ("o", "s", "^", "v", "D", ".", "x", "+") or line not in ("-", "--", "-.", ":"):
            raise ValueError("Unsupported marker or line style.")
        sizes = {}
        for key, low, high in (("markersize", .5, 15), ("linewidth", .2, 8)):
            value = d.get(key)
            try:
                value = s[key] if value is None or str(value).strip() == "" else float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{d['name']}: {key} must be a number or empty for the figure default.") from None
            if not np.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{d['name']}: {key} must be between {low:g} and {high:g} pt.")
            sizes[key] = value
        ax.plot(q[selected], obs[selected], linestyle="none", marker=marker,
                markersize=sizes["markersize"], markerfacecolor="none", markeredgewidth=.8,
                color=color, label=d.get("label", d["name"]), zorder=3)
        err = d["err"]
        if s["errors"] and err is not None:
            with_error = selected & np.isfinite(err)
            ax.errorbar(q[with_error], obs[with_error], yerr=err[with_error], fmt="none",
                        color=color, elinewidth=.65, capsize=0, zorder=2)
        if log:
            if s["clip"]:
                sim = np.where(np.isfinite(sim), np.maximum(sim, s["background"]), np.nan)
            else:
                sim[sim <= 0] = np.nan
        sim[~np.isfinite(sim)] = np.nan
        ax.plot(q, sim, linestyle=line, linewidth=sizes["linewidth"], color=color, zorder=2)
        if separate:
            ax.set_title(f"({index + 1}) {d.get('label', d['name'])}", loc="left", pad=7)
        hidden = len(obs) - int(selected.sum())
        if hidden:
            notes.append(f"{d['name']}: {hidden} measured points omitted (nonfinite, nonpositive, or below cutoff).")
        if d.get("skipped"):
            notes.append(f"{d['name']}: {d['skipped']} rows with nonfinite Q omitted on import.")
        if s["errors"] and err is not None and np.any(selected & ~np.isfinite(err)):
            notes.append(f"{d['name']}: unavailable uncertainties omitted; measured points retained.")
    if s["title"]:
        if separate:
            fig.suptitle(s["title"], fontsize=s["fontsize"])
        else:
            axes[0].set_title(s["title"])
    for index, ax in enumerate(axes):
        ax.set_yscale(s["scale"])
        ax.set_ylabel(s["ylabel"])
        if s["arrangement"] != "stack" or index == len(axes) - 1:
            ax.set_xlabel(s["xlabel"])
        for axis in ("x", "y"):
            low, high = s[axis + "min"], s[axis + "max"]
            auto_low, auto_high = getattr(ax, f"get_{axis}lim")()
            if (auto_low if low is None else low) >= (auto_high if high is None else high):
                raise ValueError(f"{axis.upper()} limits conflict with the automatic range; set both limits or clear them.")
            getattr(ax, f"set_{axis}lim")(low, high)
        ax.minorticks_on()
        ax.tick_params(which="both", direction="in", top=True, right=True)
        ax.tick_params(which="major", length=3.5, width=.7)
        ax.tick_params(which="minor", length=2, width=.5)
        ax.set_axisbelow(True)
        if s["grid"]:
            ax.grid(which="major", color="#D8DEE5", linewidth=.5)
            ax.grid(which="minor", color="#E9EDF1", linewidth=.35, alpha=.65)
        if s["legend"]:
            ax.legend(frameon=False, ncol=1 if separate else s["legendcols"], loc=s["legendloc"],
                      handletextpad=.5, columnspacing=1.2)
    return fig, notes


def render_figure(datasets, settings, extension="svg", preview=False):
    s = validate_settings(settings)
    if extension not in ("svg", "pdf", "png"):
        raise ValueError("Choose PDF, SVG, or PNG.")
    if extension == "png" and s["width"] * s["height"] * s["dpi"] ** 2 > 40_000_000:
        raise ValueError("PNG exceeds 40 megapixels. Reduce size or DPI, or export a vector PDF/SVG.")
    style = {"font.family": s["font"], "font.size": s["fontsize"],
             "axes.labelsize": s["fontsize"], "axes.titlesize": s["fontsize"],
             "xtick.labelsize": s["fontsize"], "ytick.labelsize": s["fontsize"],
             "legend.fontsize": s["fontsize"], "axes.linewidth": .7,
             "mathtext.fontset": "dejavuserif" if s["font"] == "serif" else "dejavusans",
             "pdf.fonttype": 42, "ps.fonttype": 42,
             "svg.fonttype": "path" if preview else "none", "savefig.bbox": None}
    with PLOT_LOCK, mpl.rc_context(style):
        fig, notes = build_figure(datasets, s)
        buffer = BytesIO()
        # No tight bounding-box crop: preserve the requested physical page size.
        fig.savefig(buffer, format=extension, dpi=s["dpi"] if extension == "png" else 100,
                    facecolor="white")
    return buffer.getvalue(), notes
