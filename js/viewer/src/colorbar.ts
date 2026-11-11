import { categoryColor, logRange, lut, type Mapping, mapPosition, rgbToHex } from "./color";
import type { Theme } from "./theme";
import { formatLogTick, formatTicks, logTicks, niceTicks } from "./ticks";

export interface BarSpec extends Mapping {
  title: string;
  cmap: string;
  /** Categories, for a text variable. */
  categories: string[] | null;
  /** Category colors, index-matched to `categories`; null to use the built-in palette. */
  colors: string[] | null;
  /** Column unit, drawn on the title when the title does not already end with it. */
  unit?: string;
}

const FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";
const W = 220;
const MAX_CATEGORIES = 12;
const MAX_LABEL = 26;

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

const labelWidth = (s: string) => s.length * 6.6;

/** Drops labels that would collide, always keeping the two ends. */
export function chooseTicks(ticks: { x: number; label: string }[]): { x: number; label: string }[] {
  if (ticks.length <= 2) return ticks;
  const last = ticks[ticks.length - 1];
  const fits = (a: { x: number; label: string }, b: { x: number; label: string }) =>
    b.x - a.x >= labelWidth(a.label) / 2 + labelWidth(b.label) / 2 + 8;
  const kept = [ticks[0]];
  for (const tick of ticks.slice(1, -1)) if (fits(kept[kept.length - 1], tick) && fits(tick, last)) kept.push(tick);
  kept.push(last);
  return kept;
}

const shortLabel = (s: string) => (s.length > MAX_LABEL ? `${s.slice(0, MAX_LABEL - 1)}…` : s);

/** Color bar as standalone SVG markup, so screenshots can draw it as an image. */
export function colorBarSvg(bar: BarSpec, theme: Theme, id: string): string {
  const unit = bar.unit?.trim() ?? "";
  const titleText = unit && !bar.title.endsWith(`(${unit})`) ? `${bar.title} (${unit})` : bar.title;
  const text = (x: number, y: number, s: string, extra = "") =>
    `<text x="${x}" y="${y}" font-family="${FONT}" font-size="12" fill="${theme.text}" ${extra}>${esc(s)}</text>`;
  const title = `<text x="10" y="16" font-family="${FONT}" font-size="12" font-weight="600" fill="${theme.text}">${esc(titleText)}</text>`;
  let body: string;
  let height: number;
  if (bar.categories) {
    const shown = bar.categories.slice(0, MAX_CATEGORIES);
    body = shown
      .map((c, i) => {
        const y = 26 + i * 18;
        const fill = bar.colors?.[i] ?? rgbToHex(categoryColor(i));
        const visible = shortLabel(c);
        const tip = visible === c ? "" : `<title>${esc(c)}</title>`;
        return (
          `<rect x="10" y="${y}" width="12" height="12" rx="2" fill="${fill}"/>` +
          `<text x="28" y="${y + 10}" font-family="${FONT}" font-size="12" fill="${theme.text}">${tip}${esc(visible)}</text>`
        );
      })
      .join("");
    const more = bar.categories.length - shown.length;
    height = 32 + shown.length * 18 + (more > 0 ? 16 : 4);
    if (more > 0) body += text(10, height - 8, `+${more} more`);
  } else {
    const table = lut(bar.cmap);
    const hex = (t: number) => {
      const i = Math.min(255, Math.floor(t * 256));
      return rgbToHex([table[3 * i], table[3 * i + 1], table[3 * i + 2]]);
    };
    const x0 = 10;
    const x1 = W - 10;
    const along = (t: number) => x0 + t * (x1 - x0);
    const drawTicks = (items: { x: number; label: string }[]) =>
      chooseTicks(items)
        .map((t, i, kept) => {
          const anchor = kept.length === 1 ? "middle" : i === 0 ? "start" : i === kept.length - 1 ? "end" : "middle";
          return (
            `<line x1="${t.x}" x2="${t.x}" y1="40" y2="44" stroke="${theme.muted}"/>` +
            text(t.x, 58, t.label, `text-anchor="${anchor}"`)
          );
        })
        .join("");
    const cuts = bar.bins ?? [];
    if (cuts.length) {
      const k = cuts.length + 1;
      body =
        Array.from({ length: k }, (_, c) => {
          const fill = hex(mapPosition(c === 0 ? -Infinity : cuts[c - 1], bar));
          return `<rect x="${along(c / k)}" y="28" width="${(x1 - x0) / k}" height="12" fill="${fill}"/>`;
        }).join("") + drawTicks(cuts.map((c, i) => ({ x: along((i + 1) / k), label: formatLogTick(c) })));
    } else {
      const stops = Array.from({ length: 33 }, (_, k) => {
        const t = k / 32;
        return `<stop offset="${t.toFixed(4)}" stop-color="${hex(bar.reverse ? 1 - t : t)}"/>`;
      }).join("");
      const [lo, hi] = bar.log ? logRange(bar.lo, bar.hi) : [bar.lo, bar.hi];
      const ticks = bar.log ? logTicks(lo, hi) : niceTicks(lo, hi, 4).filter((t) => t >= lo && t <= hi);
      const labels = bar.log ? ticks.map(formatLogTick) : formatTicks(ticks);
      const plain = { lo, hi, log: bar.log };
      body =
        `<defs><linearGradient id="${id}">${stops}</linearGradient></defs>` +
        `<rect x="${x0}" y="28" width="${x1 - x0}" height="12" fill="url(#${id})"/>` +
        drawTicks(ticks.map((t, i) => ({ x: along(mapPosition(t, plain)), label: labels[i] })));
    }
    height = 68;
  }
  const bg = `<rect x="0.5" y="0.5" width="${W - 1}" height="${height - 1}" rx="5" fill="${theme.panel}" fill-opacity="0.96" stroke="${theme.border}"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${height}" viewBox="0 0 ${W} ${height}">${bg}${title}${body}</svg>`;
}
