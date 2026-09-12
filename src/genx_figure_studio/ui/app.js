"use strict";
const $ = (selector) => document.querySelector(selector);
const form = $("#settings");
let settings = {}, defaults = {}, presets = {}, rows = [], api;
let revision = 0, timer, rendering = false, exporting = false, importing = false, valid = false;
let zoom = 1;

function status(message, state = "") {
  $("#status").textContent = message;
  $("#status").title = message;
  $("#status-dot").className = "status-dot " + state;
}
function showError(message) {
  $("#error").textContent = message || "";
  $("#error").hidden = !message;
}
function syncButtons() {
  const disabled = !valid || exporting || !rows.some(r => r.visible);
  $("#export").disabled = disabled;
  $("#export-top").disabled = disabled;
  $("#export-format").disabled = exporting;
  $("#clear").disabled = !rows.length || importing;
  for (const id of ["add-files", "empty-import"]) $("#" + id).disabled = !api || importing;
}
function fillForm() {
  for (const [key, value] of Object.entries(settings)) {
    const input = form.elements.namedItem(key);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = value;
    else input.value = value ?? "";
  }
  layoutControls();
  for (const input of document.querySelectorAll('.dataset-sizes input')) input.placeholder = settings[input.dataset.field] + ' (default)';
  sizePaper();
}
function layoutControls() {
  $("#panelcols-field").hidden = settings.arrangement !== "table";
  $("#layout-help").textContent = settings.arrangement === "overlay"
    ? "All selected datasets share one set of axes."
    : "One panel per selected dataset. Width and height apply to the whole figure.";
}
function sizePaper() {
  const width = Number(settings.width), height = Number(settings.height);
  if (!(width > 0 && height > 0)) return;
  const area = $("#canvas-area"), paper = $("#paper");
  const fitted = Math.min(Math.max(100, area.clientWidth - 64), Math.max(100, area.clientHeight - 60) * width / height);
  paper.style.width = fitted * zoom + "px";
  paper.style.height = fitted * zoom * height / width + "px";
  area.style.alignItems = zoom > 1 ? "flex-start" : "center";
  area.style.justifyContent = zoom > 1 ? "flex-start" : "center";
  $("#figure-size").textContent = `${(width * 25.4).toFixed(1)} × ${(height * 25.4).toFixed(1)} mm`;
  $("#zoom-label").textContent = zoom === 1 ? "Fit to view" : `${Math.round(zoom * 100)}% of fit`;
}
function datasetCards() {
  $("#dataset-list").replaceChildren();
  for (const row of rows) {
    const card = $("#dataset-template").content.firstElementChild.cloneNode(true);
    card.style.setProperty("--dataset-color", row.color);
    card.classList.toggle("muted", !row.visible);
    card.querySelector(".dataset-name").textContent = row.filename;
    card.querySelector(".dataset-name").title = row.name;
    card.querySelector(".dataset-info").textContent = `${row.points} points · ${row.hasErrors ? "with uncertainties" : "no uncertainties"}`;
    for (const input of card.querySelectorAll("[data-field]")) {
      const key = input.dataset.field;
      if (input.type === "checkbox") input.checked = row[key];
      else input.value = row[key];
      if (["markersize", "linewidth"].includes(key)) input.placeholder = settings[key] + ' (default)';
      input.addEventListener("input", () => {
        row[key] = input.type === "checkbox" ? input.checked : input.value;
        card.style.setProperty("--dataset-color", row.color);
        card.classList.toggle("muted", !row.visible);
        updateCount(); schedule();
      });
    }
    card.querySelector(".remove-dataset").addEventListener("click", async () => {
      rows = rows.filter(r => r.id !== row.id);
      datasetCards(); schedule();
      try { await api.remove_dataset(row.id); } catch (e) { showError(e.message); }
    });
    $("#dataset-list").append(card);
  }
  updateCount();
}
function updateCount() {
  $("#dataset-count").textContent = rows.length;
  $("#dataset-empty").hidden = rows.length > 0;
  $("#selection-status").textContent = rows.length ? `${rows.filter(r => r.visible).length} of ${rows.length} datasets visible` : "No datasets loaded";
  syncButtons();
}
function schedule() {
  revision++;
  valid = false;
  $("#paper").classList.toggle("stale", rows.some(r => r.visible));
  syncButtons();
  clearTimeout(timer);
  timer = setTimeout(render, 220);
}
async function render() {
  if (rendering) return;
  const current = revision;
  if (!rows.some(r => r.visible)) {
    $("#figure-image").hidden = true;
    $("#figure-empty").hidden = false;
    $("#figure-empty h2").textContent = rows.length ? "Choose a dataset to display." : "A figure worth publishing.";
    $("#paper").classList.remove("stale");
    $("#notes").hidden = true;
    valid = false; showError(""); syncButtons();
    status(rows.length ? "All datasets hidden" : "Ready to import GenX data");
    return;
  }
  rendering = true;
  status("Rendering figure…", "busy");
  try {
    const result = await api.preview(rows, settings);
    if (current !== revision) return;
    if (result.error) throw new Error(result.error);
    $("#figure-image").src = result.image;
    $("#figure-image").hidden = false;
    $("#figure-empty").hidden = true;
    $("#paper").classList.remove("stale");
    $("#notes").textContent = result.notes.join("\n");
    $("#notes").hidden = !result.notes.length;
    showError(""); valid = true; sizePaper();
    status("Preview updated · ready to export");
  } catch (e) {
    if (current === revision) { valid = false; showError(e.message); status("Check figure settings", "failed"); }
  } finally {
    rendering = false; syncButtons();
    if (current !== revision) render();
  }
}
async function importData() {
  if (!api || importing) return;
  importing = true; syncButtons(); status("Select GenX exports…", "busy");
  try {
    const result = await api.load_files();
    rows.push(...result.datasets); datasetCards();
    if (result.datasets.length) { revision++; valid = false; await render(); }
    else status("Import cancelled or no valid files selected");
    if (result.errors.length) { showError(result.errors.join("\n")); status("Some files could not be imported", "failed"); }
  } catch (e) { showError(e.message); status("Import failed", "failed"); }
  finally { importing = false; syncButtons(); }
}
async function exportFigure() {
  if (!valid || exporting) return;
  exporting = true; syncButtons();
  const chosenFormat = $("#export-format").value;
  status(`Preparing ${chosenFormat.toUpperCase()}…`, "busy");
  try {
    const result = await api.export(rows, settings, chosenFormat);
    if (result.error) throw new Error(result.error);
    status(result.cancelled ? "Export cancelled" : `Exported ${result.path}`);
    showError("");
  } catch (e) { showError(e.message); status("Export failed", "failed"); }
  finally { exporting = false; syncButtons(); }
}
form.addEventListener("submit", event => event.preventDefault());
form.addEventListener("input", event => {
  const input = event.target;
  if (!input.name) return;
  settings[input.name] = input.type === "checkbox" ? input.checked : input.value;
  if (["width", "height", "fontsize", "markersize", "linewidth", "legendcols"].includes(input.name)) $("#preset").value = "custom";
  layoutControls();
  if (["markersize", "linewidth"].includes(input.name)) {
    for (const item of document.querySelectorAll(`.dataset-sizes [data-field="${input.name}"]`)) item.placeholder = input.value + ' (default)';
  }
  schedule();
});
// The DPI input belongs to the form but is rendered in the export section.
$("[name=dpi]").addEventListener("input", event => { settings.dpi = event.target.value; schedule(); });
$("#preset").addEventListener("change", event => {
  const preset = presets[event.target.value];
  if (preset) { Object.assign(settings, preset); fillForm(); schedule(); }
});
$("#reset").addEventListener("click", () => { settings = {...defaults}; $("#preset").value = "double"; fillForm(); schedule(); });
$("#auto-limits").addEventListener("click", () => { Object.assign(settings, {xmin:"", xmax:"", ymin:"", ymax:""}); fillForm(); schedule(); });
$("#add-files").addEventListener("click", () => importData());
$("#empty-import").addEventListener("click", () => importData());
$("#clear").addEventListener("click", async () => {
  const previous = rows; rows = []; datasetCards(); schedule();
  try { for (const row of previous) await api.remove_dataset(row.id); } catch (e) { showError(e.message); }
});
$("#export").addEventListener("click", exportFigure);
$("#export-top").addEventListener("click", exportFigure);
function updateExportFormat() {
  const format = $("#export-format").value;
  for (const id of ["export", "export-top"]) $("#" + id).textContent = `Export ${format.toUpperCase()} ↗`;
  $("#format-tag").textContent = format === "png" ? "RASTER" : "VECTOR";
  $("#dpi-field").hidden = format !== "png";
  $("#format-help").textContent = {pdf:"Vector artwork with embedded fonts. Best for manuscript submission.", svg:"Editable vector artwork. Text uses DejaVu fonts; install them in your illustration editor.", png:"High-resolution raster with a white background. DPI applies to PNG only."}[format];
}
$("#export-format").addEventListener("change", updateExportFormat);
updateExportFormat();
$("#zoom-in").addEventListener("click", () => { zoom = Math.min(3, zoom + .25); sizePaper(); });
$("#zoom-out").addEventListener("click", () => { zoom = Math.max(.5, zoom - .25); sizePaper(); });
$("#zoom-fit").addEventListener("click", () => { zoom = 1; sizePaper(); });
new ResizeObserver(sizePaper).observe($("#canvas-area"));
window.addEventListener("pywebviewready", async () => {
  try {
    api = window.pywebview.api;
    const data = await api.bootstrap();
    defaults = data.settings; settings = {...defaults}; presets = data.presets;
    fillForm(); syncButtons(); $("#reset").disabled = false;
    status("Ready to import GenX data");
  } catch (e) { showError(e.message); status("Could not connect to plotting engine", "failed"); }
});
