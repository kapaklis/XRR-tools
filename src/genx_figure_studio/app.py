"""Native webview shell with local Python/Matplotlib rendering."""
import base64
from pathlib import Path
import os
import tempfile
import threading
import uuid

from .plotting import COLORS, DEFAULTS, LABELS, PRESETS, read_genx_dat, render_figure


class StudioAPI:
    def __init__(self):
        self._window = None
        self._datasets = {}
        self._lock = threading.Lock()

    def bootstrap(self):
        return dict(settings=DEFAULTS, presets=PRESETS)

    def _register(self, data):
        with self._lock:
            identifier = uuid.uuid4().hex
            color = COLORS[len(self._datasets) % len(COLORS)]
            self._datasets[identifier] = data
        label = LABELS.get(data["channel"], data["name"])
        if data["channel"] and data["condition"]:
            label += " · " + data["condition"]
        return dict(id=identifier, name=data["name"], filename=Path(data["path"]).name,
                    label=label, color=color, marker="o", line="-", visible=True,
                    markersize="", linewidth="",
                    points=len(data["q"]), hasErrors=data["err"] is not None)

    def load_files(self):
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                    file_types=("GenX exports (*.dat;*.txt)", "All files (*.*)"))
        loaded, errors = [], []
        for path in paths or ():
            try:
                loaded.append(self._register(read_genx_dat(path)))
            except (OSError, ValueError) as exc:
                errors.append(f"{Path(path).name}: {exc}")
        return dict(datasets=loaded, errors=errors)

    def remove_dataset(self, identifier):
        with self._lock:
            self._datasets.pop(identifier, None)

    def _resolve(self, rows):
        with self._lock:
            return [{**self._datasets[row["id"]], **{key: row[key] for key in
                    ("label", "color", "marker", "line", "visible", "markersize", "linewidth")
                    if key in row}} for row in rows]

    def preview(self, rows, settings):
        try:
            svg, notes = render_figure(self._resolve(rows), settings, preview=True)
            return dict(image="data:image/svg+xml;base64," + base64.b64encode(svg).decode(), notes=notes)
        except (ValueError, KeyError, TypeError) as exc:
            return dict(error=str(exc))

    def export(self, rows, settings, extension):
        try:
            content, notes = render_figure(self._resolve(rows), settings, extension)
            return save_figure(self._window, content, extension, "reflectivity", notes)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return dict(error=str(exc))


def save_figure(window, content, extension, filename, notes=()):
    """Save rendered bytes through a native dialog, replacing files atomically."""
    import webview
    paths = window.create_file_dialog(webview.FileDialog.SAVE,
                save_filename=f"{filename}.{extension}",
                file_types=(f"{extension.upper()} figure (*.{extension})",))
    if not paths:
        return dict(cancelled=True)
    path = Path(paths if isinstance(paths, str) else paths[0])
    if not path.suffix:
        path = path.with_suffix("." + extension)
        if path.exists() and not window.create_confirmation_dialog(
                "Replace figure?", f"{path.name} already exists. Replace it?"):
            return dict(cancelled=True)
    if path.suffix.lower() != "." + extension:
        raise ValueError(f"Use a .{extension} filename for this export format.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = output.name
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return dict(path=str(path), notes=notes)


def main():
    import webview
    api = StudioAPI()
    assets = Path(__file__).with_name("ui")
    html = (assets / "index.html").read_text(encoding="utf-8")
    html = html.replace("/* STUDIO_CSS */", (assets / "style.css").read_text(encoding="utf-8"))
    html = html.replace("/* STUDIO_JS */", (assets / "app.js").read_text(encoding="utf-8"))
    api._window = webview.create_window("GenX Figure Studio", html=html, js_api=api,
                        width=1440, height=940, min_size=(1024, 700), background_color="#F3F5F7",
                        text_select=True)
    webview.start()


if __name__ == "__main__":
    main()
