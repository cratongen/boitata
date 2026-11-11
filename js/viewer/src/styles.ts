export const CSS = /* css */ `
:host { all: initial; display: block; }
.btv-root {
  position: relative; width: 100%; overflow: hidden; outline: none;
  background: var(--btv-bg); color: var(--btv-text);
  font: 12px/1.35 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased; user-select: none;
}
.btv-root canvas { display: block; }
.btv-root *, .btv-root *::before, .btv-root *::after { box-sizing: border-box; }
.btv-labels { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.btv-label { position: absolute; left: 0; top: 0; white-space: nowrap; color: var(--btv-muted); font-size: 11px;
  font-variant-numeric: tabular-nums; }
.btv-label.btv-title { color: var(--btv-text); font-weight: 600; }
.btv-gizmo { position: absolute; right: 8px; bottom: 8px; cursor: pointer; overflow: visible; }
.btv-gizmo .btv-gizmo-face:hover .btv-face { fill: var(--btv-accent); fill-opacity: .18; stroke: var(--btv-accent); }

.btv-panel {
  position: absolute; top: 10px; right: 10px; width: 288px; max-height: calc(100% - 20px);
  display: flex; flex-direction: column; background: var(--btv-panel); border: 1px solid var(--btv-border);
  border-radius: 6px; box-shadow: 0 4px 16px rgba(0, 0, 0, .10); overflow: hidden;
}
.btv-panel[hidden], .btv-open[hidden] { display: none; }
.btv-head { display: flex; align-items: center; gap: 6px; padding: 6px 8px 6px 12px; border-bottom: 1px solid var(--btv-border); }
.btv-cluster { display: inline-flex; align-items: center; gap: 1px; padding: 2px; background: var(--btv-raised); border-radius: 6px; }
.btv-settings .btv-cluster { background: var(--btv-panel); }
.btv-head .btv-end { margin-left: auto; }
.btv-cluster .btv-icon { width: 26px; height: 26px; border-radius: 4px; }
.btv-head .btv-brand { flex: 1; font-weight: 600; letter-spacing: .02em; }
.btv-body { overflow-y: auto; padding: 2px 0 10px; }
.btv-icon {
  display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; padding: 0;
  border: 0; border-radius: 4px; background: transparent; color: var(--btv-muted); cursor: pointer; flex: none;
}
.btv-icon:hover { background: var(--btv-raised); color: var(--btv-text); }
.btv-icon:active:not(:disabled):not([aria-disabled=true]) { background: color-mix(in srgb, var(--btv-text) 14%, var(--btv-raised)); }
.btv-icon.btv-on { color: var(--btv-accent); background: color-mix(in srgb, var(--btv-accent) 12%, transparent); }
.btv-icon svg, .btv-section svg, .btv-cond-head > svg { width: 16px; height: 16px; }
.btv-open { position: absolute; top: 10px; right: 10px; width: 34px; height: 34px; background: var(--btv-panel);
  border: 1px solid var(--btv-border); box-shadow: 0 4px 16px rgba(0, 0, 0, .10); }
.btv-section { display: flex; align-items: center; gap: 6px; width: 100%; margin-top: 2px; padding: 8px 12px 2px;
  border: 0; border-top: 1px solid var(--btv-border); background: none; color: var(--btv-muted); font: inherit;
  font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; cursor: pointer; text-align: left; }
.btv-body > .btv-section:first-child { margin-top: 2px; border-top: 0; }
.btv-section svg { width: 16px; height: 16px; flex: none; }
.btv-section .btv-count { margin-left: auto; font-weight: 500; letter-spacing: 0; font-variant-numeric: tabular-nums; }
.btv-group { display: flex; flex-direction: column; gap: 1px; padding: 2px 8px 2px; }
.btv-row { display: flex; align-items: center; gap: 6px; padding: 2px 4px; border-radius: 4px; min-height: 30px; }
.btv-row:hover { background: var(--btv-raised); }
.btv-row:active { background: color-mix(in srgb, var(--btv-text) 8%, var(--btv-raised)); }
.btv-row.btv-selected { background: color-mix(in srgb, var(--btv-accent) 12%, var(--btv-panel)); }
.btv-row.btv-selected:hover { background: color-mix(in srgb, var(--btv-accent) 18%, var(--btv-panel)); }
.btv-row.btv-off .btv-name, .btv-row.btv-off .btv-key { opacity: .45; }
.btv-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.btv-key { flex: none; width: 36px; height: 8px; border-radius: 2px; border: 1px solid var(--btv-border); }
.btv-key.btv-swatch { width: 12px; height: 12px; border-radius: 3px; }
.btv-settings { margin: 2px 10px 8px; padding: 6px 8px 8px; display: grid; grid-template-columns: 72px minmax(0, 1fr);
  gap: 6px 10px; align-items: center; background: var(--btv-raised); border: 1px solid var(--btv-border); border-radius: 6px; }
.btv-settings label { color: var(--btv-muted); font-size: 11px; line-height: 1.2; }
.btv-settings label:has(+ .btv-chips), .btv-settings label:has(+ .btv-range) { align-self: start; padding-top: 6px; }
.btv-rule { grid-column: 1 / -1; height: 1px; margin: 2px 0; background: var(--btv-border); }
.btv-settings select, .btv-settings input[type=number], .btv-settings input[type=text] {
  width: 100%; min-width: 0; height: 26px; padding: 0 6px; font: inherit; color: var(--btv-text);
  background: var(--btv-panel); border: 1px solid var(--btv-border); border-radius: 4px; }
.btv-settings input[type=number] { font-variant-numeric: tabular-nums; }
.btv-settings input[type=color] { width: 40px; height: 22px; padding: 0; border: 1px solid var(--btv-border);
  border-radius: 4px; background: none; }
.btv-range { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.btv-range .btv-icon { width: 22px; height: 22px; }
.btv-root input[type=range] { width: 100%; accent-color: var(--btv-accent); }
.btv-shot { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-bottom: 1px solid var(--btv-border); }
.btv-shot[hidden] { display: none; }
.btv-seg { display: inline-flex; border: 1px solid var(--btv-border); border-radius: 4px; overflow: hidden; }
.btv-seg button { flex: 1; border: 0; padding: 3px 6px; white-space: nowrap; font: inherit; background: none; color: var(--btv-muted); cursor: pointer; }
.btv-seg button.btv-on { background: var(--btv-accent); color: var(--btv-bg); }
.btv-seg button:not(.btv-on):hover { background: var(--btv-raised); color: var(--btv-text); }
.btv-seg button:not(.btv-on):active { background: color-mix(in srgb, var(--btv-text) 10%, var(--btv-raised)); }
.btv-seg button + button { border-left: 1px solid var(--btv-border); }
.btv-settings .btv-seg { display: flex; }
.btv-root button:focus-visible { outline: 2px solid var(--btv-accent); outline-offset: 1px; }
.btv-view { margin: 2px 10px 8px; }
.btv-tools { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.btv-icon.btv-tool { width: 26px; height: 26px; border: 1px solid var(--btv-border); }
.btv-cluster .btv-icon.btv-tool { border: 0; }
.btv-icon.btv-tool[aria-pressed=true] { background: var(--btv-accent); border-color: var(--btv-accent); color: var(--btv-bg); }
.btv-icon.btv-tool[aria-pressed=true]:hover { filter: brightness(1.08); }
.btv-icon.btv-tool[aria-pressed=true]:active { filter: brightness(.94); }
.btv-shot label { display: flex; align-items: center; gap: 4px; color: var(--btv-muted); flex: 1; }
.btv-shot label input { accent-color: var(--btv-accent); margin: 0; }
.btv-mark { flex: none; width: 12px; height: 12px; color: var(--btv-accent); }
.btv-readout { margin: 0 8px 4px 38px; color: var(--btv-muted); font-size: 11px; line-height: 1.3; font-variant-numeric: tabular-nums; }
.btv-readout[hidden] { display: none; }
.btv-filter { grid-column: 1 / -1; display: flex; flex-direction: column; gap: 8px; margin-top: 2px; padding-top: 8px;
  border-top: 1px solid var(--btv-border); }
.btv-filter-head { display: flex; align-items: center; justify-content: space-between; }
.btv-filter-head label { padding-top: 0; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
.btv-icon.btv-add { width: auto; height: 22px; gap: 3px; padding: 0 7px 0 4px; font: inherit; border: 1px solid var(--btv-border); }
.btv-icon.btv-add svg { width: 16px; height: 16px; }
.btv-note { color: var(--btv-muted); font-size: 11px; }
.btv-cond { border: 1px solid var(--btv-border); border-radius: 5px; padding: 4px 8px 8px; background: var(--btv-panel); }
.btv-cond-head { display: flex; align-items: center; gap: 5px; min-height: 24px; }
.btv-cond-head > svg { flex: none; width: 16px; height: 16px; color: var(--btv-accent); }
.btv-cond-head .btv-name { font-weight: 600; }
.btv-cond-head .btv-icon { width: 22px; height: 22px; }
.btv-hist { height: 34px; margin-top: 2px; }
.btv-hist svg { display: block; width: 100%; height: 100%; }
.btv-bars-all { fill: var(--btv-muted); opacity: .35; }
.btv-bars-on { fill: var(--btv-accent); }
.btv-track { position: relative; height: 16px; margin: 0 6px 6px; cursor: pointer; touch-action: none; }
.btv-track::before { content: ""; position: absolute; left: -6px; right: -6px; top: 7px; height: 2px; border-radius: 1px;
  background: var(--btv-border); }
.btv-fill { position: absolute; top: 7px; height: 2px; background: var(--btv-accent); }
.btv-handle { position: absolute; top: 2px; width: 12px; height: 12px; margin-left: -6px; border-radius: 50%;
  background: var(--btv-bg); border: 2px solid var(--btv-accent); }
.btv-handle:focus-visible { outline: 2px solid var(--btv-accent); outline-offset: 1px; }
.btv-quick { display: flex; gap: 4px; margin: 2px 0 4px; }
.btv-quick button { border: 1px solid var(--btv-border); border-radius: 4px; padding: 1px 8px; font: inherit;
  background: none; color: var(--btv-muted); cursor: pointer; }
.btv-quick button:hover, .btv-chip:hover { background: var(--btv-raised); color: var(--btv-text); }
.btv-quick button:active, .btv-chip:active { background: color-mix(in srgb, var(--btv-text) 10%, var(--btv-raised)); }
.btv-list { max-height: 150px; overflow-y: auto; }
.btv-list label { display: flex; align-items: center; gap: 6px; min-height: 22px; color: var(--btv-text); cursor: pointer; }
.btv-list input { margin: 0; accent-color: var(--btv-accent); }
.btv-list .btv-count { color: var(--btv-muted); font-variant-numeric: tabular-nums; }
.btv-filter > select { width: 100%; height: 24px; padding: 0 6px; font: inherit; color: var(--btv-text);
  background: var(--btv-raised); border: 1px solid var(--btv-border); border-radius: 4px; }
.btv-bars { position: absolute; left: 12px; bottom: 12px; display: flex; flex-direction: column-reverse; gap: 10px;
  pointer-events: none; }
.btv-bar { pointer-events: auto; cursor: grab; touch-action: none; }
.btv-bar.btv-moved { position: absolute; }
.btv-bar svg { display: block; }
.btv-scale { position: absolute; left: 248px; bottom: 12px; pointer-events: none; }
.btv-scale svg { display: block; }
.btv-chip { font: inherit; font-size: 11px; padding: 0 6px; border-radius: 4px; border: 1px solid var(--btv-border);
  background: var(--btv-panel); color: var(--btv-text); cursor: pointer; white-space: nowrap; }
.btv-chips { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; }
.btv-chips .btv-chip { padding: 3px 4px; text-align: center; }
.btv-check { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.btv-settings select:hover, .btv-settings input:hover, .btv-filter select:hover {
  border-color: color-mix(in srgb, var(--btv-muted) 50%, var(--btv-border)); }
.btv-settings select:focus-visible, .btv-settings input:focus-visible, .btv-filter select:focus-visible {
  outline: 2px solid var(--btv-accent); outline-offset: 1px; }
.btv-icon:disabled, .btv-icon[aria-disabled=true] {
  color: color-mix(in srgb, var(--btv-muted) 42%, var(--btv-panel)); cursor: not-allowed; }
.btv-icon.btv-tool:disabled {
  background: color-mix(in srgb, var(--btv-panel) 72%, var(--btv-raised));
  border-color: var(--btv-border); color: color-mix(in srgb, var(--btv-muted) 38%, var(--btv-panel)); }
.btv-icon:disabled:hover, .btv-icon[aria-disabled=true]:hover { background: transparent; color: color-mix(in srgb, var(--btv-muted) 42%, var(--btv-panel)); }
.btv-icon.btv-tool:disabled:hover { background: color-mix(in srgb, var(--btv-panel) 72%, var(--btv-raised)); }
.btv-pair { flex-wrap: nowrap; }
.btv-pair input[type=range] { flex: 1; min-width: 0; }
.btv-settings .btv-range input[type=number] { width: auto; flex: 1 1 4.5rem; min-width: 4.5rem; }
.btv-settings .btv-pair input[type=number] { width: 4.5rem; flex: none; min-width: 0; }
.btv-hint { grid-column: 1 / -1; line-height: 1.4; }
.btv-sweep { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.btv-sweep line { stroke: var(--btv-accent); stroke-width: 2; stroke-dasharray: 6 4; }
.btv-sweep text { fill: var(--btv-text); font-size: 11px; paint-order: stroke; stroke: var(--btv-bg); stroke-width: 3px; }
.btv-card { position: absolute; z-index: 2; min-width: 190px; max-width: 300px; max-height: calc(100% - 16px);
  overflow-y: auto; background: var(--btv-panel); border: 1px solid var(--btv-border); border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, .14); user-select: text; }
.btv-card[hidden] { display: none; }
.btv-card-head { display: flex; align-items: center; gap: 4px; padding: 4px 4px 4px 10px; font-weight: 600;
  border-bottom: 1px solid var(--btv-border); }
.btv-card dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 14px; margin: 0; padding: 6px 10px 8px; }
.btv-card dt { color: var(--btv-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
.btv-card dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.btv-help { left: 50%; top: 50%; transform: translate(-50%, -50%); z-index: 3; max-width: 340px; }
.btv-help dt { max-width: none; }
.btv-help dd { text-align: left; white-space: normal; color: var(--btv-text); }
.btv-help kbd { font: 11px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; padding: 0 5px; color: var(--btv-text);
  background: var(--btv-raised); border: 1px solid var(--btv-border); border-radius: 3px; }
.btv-root:focus-visible::after { content: ""; position: absolute; inset: 0; pointer-events: none;
  border: 2px solid var(--btv-accent); opacity: .6; }
.btv-root:fullscreen { width: 100%; height: 100% !important; }
.btv-mode { position: absolute; top: 12px; left: 12px; z-index: 2; display: flex; align-items: center; gap: 8px;
  height: 28px; padding: 0 8px 0 10px; background: var(--btv-panel); color: var(--btv-text);
  border: 1px solid var(--btv-accent); border-radius: 999px; box-shadow: 0 4px 16px rgba(0, 0, 0, .12);
  font-weight: 600; pointer-events: none; }
.btv-mode[hidden] { display: none; }
.btv-mode-hint { color: var(--btv-muted); font-weight: 500; }
.btv-mode kbd { font: 11px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; padding: 0 5px; color: var(--btv-text);
  background: var(--btv-raised); border: 1px solid var(--btv-border); border-radius: 3px; }
.btv-root.btv-mode-draw canvas, .btv-root.btv-mode-measure canvas { cursor: crosshair; }
.btv-root.btv-plane-hover canvas { cursor: grab; }
.btv-root.btv-plane-drag canvas { cursor: grabbing; }
.btv-root.btv-mode-draw, .btv-root.btv-mode-measure, .btv-root.btv-mode-section { box-shadow: inset 0 0 0 2px var(--btv-accent); }
@media (prefers-reduced-motion: no-preference) {
  .btv-icon, .btv-row, .btv-seg button, .btv-chip, .btv-quick button, .btv-handle, .btv-mode {
    transition: background-color .12s ease, color .12s ease, border-color .12s ease, opacity .12s ease;
  }
}
.btv-card hr { grid-column: 1 / -1; width: 100%; margin: 3px 0; border: 0; border-top: 1px solid var(--btv-border); }
`;
