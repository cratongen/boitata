import * as THREE from "three";
import type { Box, Vec3 } from "./bounds";

/** Segments a section holds at most: each takes four vec4 uniforms in every material. */
export const MAX_SEGMENTS = 16;
/** Views looking down at least this steeply pick a quick cut's ends on a level plane, others on an upright one. */
const LEVEL_PICK_DIP = 20;

type XY = [number, number];
type Plane = [number, number, number, number];

/** A section as Python reads and writes it: real-world points, width in meters (null for the default), dip. */
export interface SectionState {
  points: number[][];
  width: number | null;
  dip: number;
  unfolded: boolean;
}

/** One straight piece of a section, in local coordinates. */
export interface Segment {
  a: XY;
  /** Unit direction in plan. */
  u: XY;
  length: number;
  /** Distance along the section where the segment starts. */
  chainage: number;
  /** Plane through the segment, tilted by the dip: signed distance `dot(n, p) + d`. */
  slab: Plane;
  /** Upright planes bounding the segment, positive inside: across its start, and the bisectors at bends. */
  start: Plane;
  end: Plane;
  /** Unfolding motion in plan, `x' = c x + s y + tx, y' = -s x + c y + ty`, as (c, s, tx, ty). */
  move: Plane;
}

export interface Section {
  segments: Segment[];
  /** Elevation the trace hinges on when the section dips. */
  z: number;
  half: number;
  dip: number;
  length: number;
}

const dot2 = (a: XY, b: XY) => a[0] * b[0] + a[1] * b[1];
const plane = (n: XY, p: XY): Plane => [n[0], n[1], 0, -dot2(n, p)];
const side = (q: Plane, p: Vec3) => q[0] * p[0] + q[1] * p[1] + q[2] * p[2] + q[3];

/** Vertices with consecutive repeats in plan dropped. */
export function distinct(points: XY[]): XY[] {
  return points.filter((p, i) => i === 0 || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1]);
}

/**
 * A section along a polyline in plan, `width` thick around the surface that runs through it at elevation `z` and
 * dips `dip` degrees to the right of the direction it is drawn in (90 is upright). Null for fewer than two
 * distinct vertices.
 */
export function buildSection(points: XY[], z: number, width: number, dip: number): Section | null {
  const p = distinct(points).slice(0, MAX_SEGMENTS + 1);
  if (p.length < 2) return null;
  const d = THREE.MathUtils.degToRad(dip);
  const units = p.slice(1).map((q, i) => {
    const step: XY = [q[0] - p[i][0], q[1] - p[i][1]];
    const length = Math.hypot(...step);
    return { u: [step[0] / length, step[1] / length] as XY, length };
  });
  const bisector = (i: number): XY => {
    const [a, b] = [units[i - 1].u, units[i].u];
    const s: XY = [a[0] + b[0], a[1] + b[1]];
    const n = Math.hypot(...s);
    return n > 1e-9 ? [s[0] / n, s[1] / n] : b;
  };
  let chainage = 0;
  const segments = units.map(({ u, length }, i) => {
    const a = p[i];
    const n: XY = [u[1], -u[0]];
    const normal: Vec3 = [Math.sin(d) * n[0], Math.sin(d) * n[1], Math.cos(d)];
    const slab: Plane = [...normal, -(normal[0] * a[0] + normal[1] * a[1] + normal[2] * z)];
    const start = plane(i === 0 ? u : bisector(i), a);
    const toward = i === units.length - 1 ? u : bisector(i + 1);
    const end = plane([-toward[0], -toward[1]], p[i + 1]);
    const move: Plane = [u[0], u[1], chainage - (u[0] * a[0] + u[1] * a[1]), u[1] * a[0] - u[0] * a[1]];
    const segment = { a, u, length, chainage, slab, start, end, move };
    chainage += length;
    return segment;
  });
  return { segments, z, half: width / 2, dip, length: chainage };
}

/** Whether a point lies in the slab: within half the width of the surface, between the section's ends. */
export function inSlab(s: Section, p: Vec3): boolean {
  return s.segments.some((g) => side(g.start, p) >= 0 && side(g.end, p) >= 0 && Math.abs(side(g.slab, p)) <= s.half);
}

/**
 * Where a box (`size` along each of the unit `axes` around `center`) lies against the slab: 0 wholly outside
 * every segment's stretch, 2 wholly inside one, 1 across a face. Conservative: a box called outside is outside.
 */
export function boxInSlab(s: Section, center: Vec3, axes: Vec3[], size: Vec3): 0 | 1 | 2 {
  let out: 0 | 1 | 2 = 0;
  for (const g of s.segments) {
    const [a, b, c, d] = g.slab;
    const planes: Plane[] = [g.start, g.end, [-a, -b, -c, s.half - d], [a, b, c, d + s.half]];
    let inside = true;
    let outside = false;
    for (const q of planes) {
      const at = side(q, center);
      let r = 0;
      for (let k = 0; k < 3; k++) r += (Math.abs(q[0] * axes[k][0] + q[1] * axes[k][1] + q[2] * axes[k][2]) * size[k]) / 2;
      if (at + r < 0) outside = true;
      if (at - r < 0) inside = false;
    }
    if (inside) return 2;
    if (!outside) out = 1;
  }
  return out;
}

/** Index of the segment whose stretch holds a point: the first one whose end it has not passed. */
export function segmentOf(s: Section, p: Vec3): number {
  const last = s.segments.length - 1;
  for (let j = 0; j < last; j++) if (side(s.segments[j].end, p) >= 0) return j;
  return last;
}

/** A point of the unfolded section: distance along it, offset to the left of its direction, elevation. */
export function unfold(s: Section, p: Vec3, ref: Vec3 = p): Vec3 {
  const [c, sn, tx, ty] = s.segments[segmentOf(s, ref)].move;
  return [c * p[0] + sn * p[1] + tx, -sn * p[0] + c * p[1] + ty, p[2]];
}

/** Unit plan direction of a bearing in degrees clockwise from north. */
const bearing = (azimuth: number): XY => {
  const a = THREE.MathUtils.degToRad(azimuth);
  return [Math.sin(a), Math.cos(a)];
};

/** Bearing from a cut's first point to its last, in degrees clockwise from north, in [0, 360). */
export function cutAzimuth(points: XY[]): number {
  const p = distinct(points);
  const [a, b] = [p[0], p[p.length - 1]];
  return (THREE.MathUtils.radToDeg(Math.atan2(b[0] - a[0], b[1] - a[1])) + 360) % 360;
}

/** Ends of a straight cut `length` long through `center`, drawn along `azimuth`. */
export function presetCut(center: XY, azimuth: number, length: number): [XY, XY] {
  const u = bearing(azimuth);
  return [
    [center[0] - (u[0] * length) / 2, center[1] - (u[1] * length) / 2],
    [center[0] + (u[0] * length) / 2, center[1] + (u[1] * length) / 2],
  ];
}

/** A cut moved `distance` square to its first segment, toward the right of the direction it is drawn in. */
export function stepCut(points: XY[], distance: number): XY[] {
  const p = distinct(points);
  const step: XY = [p[1][0] - p[0][0], p[1][1] - p[0][1]];
  const n = Math.hypot(...step) || 1;
  const right: XY = [step[1] / n, -step[0] / n];
  return points.map((q) => [q[0] + right[0] * distance, q[1] + right[1] * distance]);
}

/**
 * A straight cut `length` long through the middle of a cut's ends: along its bearing for a long section, square to
 * it for a cross section.
 */
export function orthogonalCut(points: XY[], kind: "long" | "cross", length: number): [XY, XY] {
  const p = distinct(points);
  const [a, b] = [p[0], p[p.length - 1]];
  const azimuth = cutAzimuth(points) + (kind === "cross" ? 90 : 0);
  return presetCut([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], azimuth, length);
}

/** Bearing a camera looks along to see a cut at `azimuth` face on, its start on the left. */
export const faceOn = (azimuth: number) => (azimuth + 270) % 360;

const sub3 = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add3 = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const mul3 = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s];
const dot3 = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross3 = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const len3 = (a: Vec3) => Math.hypot(a[0], a[1], a[2]);

/**
 * Unit normal of a straight section striking `azimuth` degrees clockwise from north and dipping `dip` degrees
 * to the right of that direction (0 is level, 90 upright).
 */
export function planeNormal(azimuth: number, dip: number): Vec3 {
  const u = bearing(azimuth);
  const right: XY = [u[1], -u[0]];
  const d = THREE.MathUtils.degToRad(dip);
  return [Math.sin(d) * right[0], Math.sin(d) * right[1], Math.cos(d)];
}

/**
 * A straight section of `length` whose surface passes through `origin`, striking `azimuth` and dipping `dip`.
 * The trace is centered on the plan of `origin` and hinged at its elevation.
 */
export function planeSection(
  origin: Vec3,
  azimuth: number,
  dip: number,
  length: number,
): { points: [XY, XY]; z: number; dip: number } {
  return { points: presetCut([origin[0], origin[1]], azimuth, length), z: origin[2], dip };
}

/** Pose of a straight cut. Null unless it has two distinct points in plan. */
export function planePose(
  points: XY[],
  z: number,
  dip: number,
): { origin: Vec3; normal: Vec3; azimuth: number; length: number } | null {
  const p = distinct(points);
  if (p.length !== 2) return null;
  const step: XY = [p[1][0] - p[0][0], p[1][1] - p[0][1]];
  const length = Math.hypot(...step);
  if (length < 1e-9) return null;
  const azimuth = cutAzimuth(p);
  const origin: Vec3 = [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2, z];
  return { origin, normal: planeNormal(azimuth, dip), azimuth, length };
}

/** Signed offset of `hit` from `grab` along a unit `normal`. */
export const projectDrag = (grab: Vec3, hit: Vec3, normal: Vec3) => dot3(sub3(hit, grab), normal);

/**
 * Unit normal of the plane that contains `axis` and faces `forward`. Null when `forward` lies within about
 * 14 degrees of `axis`, where that plane would be edge-on to the view and a small pointer move would throw
 * the slide.
 */
export function dragPlaneNormal(axis: Vec3, forward: Vec3): Vec3 | null {
  const perp = sub3(forward, mul3(axis, dot3(axis, forward)));
  const n = len3(perp);
  if (n < 0.25) return null;
  return [perp[0] / n, perp[1] / n, perp[2] / n];
}

/** Where `ray` meets the plane through `point` with unit `normal`. Null when it is parallel or the hit is behind the ray. */
export function rayPlane(ray: Ray, point: Vec3, normal: Vec3): Vec3 | null {
  const denom = dot3(normal, ray.direction);
  if (Math.abs(denom) < 1e-9) return null;
  const t = dot3(normal, sub3(point, ray.origin)) / denom;
  if (t <= 0) return null;
  return add3(ray.origin, mul3(ray.direction, t));
}

/**
 * Signed distance to slide a plane along `normal` so the pointer follows. The ray meets the plane that contains
 * `normal` and faces `forward`, through `grab`, and that hit is projected onto `normal`. Null when the plane is
 * undefined or the ray misses it.
 */
export function slideAlongNormal(ray: Ray, grab: Vec3, normal: Vec3, forward: Vec3): number | null {
  const face = dragPlaneNormal(normal, forward);
  if (!face) return null;
  const hit = rayPlane(ray, grab, face);
  return hit ? projectDrag(grab, hit, normal) : null;
}

/**
 * Screen fallback when the plane faces the camera, so `normal` has no usable direction on screen. A mostly
 * vertical normal tracks the vertical pointer travel (up is positive when the normal points up); any other
 * tracks the horizontal travel, positive with the normal's stronger plan component.
 */
export function faceOnSlide(dx: number, dy: number, normal: Vec3, perPixel: number): number {
  if (Math.abs(normal[2]) >= Math.abs(normal[0]) && Math.abs(normal[2]) >= Math.abs(normal[1]))
    return -dy * perPixel * Math.sign(normal[2] || 1);
  const sign = Math.abs(normal[0]) >= Math.abs(normal[1]) ? Math.sign(normal[0] || 1) : Math.sign(normal[1] || 1);
  return dx * perPixel * sign;
}

const BOX_EDGES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 5], [5, 6], [6, 7], [7, 4],
  [0, 4], [1, 5], [2, 6], [3, 7],
];

/** Convex polygon where the plane through `origin` with unit `normal` cuts `box`, ordered around the normal. Empty when it misses. */
export function clipPlane(origin: Vec3, normal: Vec3, box: Box): Vec3[] {
  const [x0, y0, z0] = box.min;
  const [x1, y1, z1] = box.max;
  const corners: Vec3[] = [
    [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
  ];
  const side = corners.map((p) => dot3(normal, sub3(p, origin)));
  const span = Math.max(x1 - x0, y1 - y0, z1 - z0, 1);
  const tol = 1e-7 * span;
  const hits: Vec3[] = [];
  for (const [i, j] of BOX_EDGES) {
    const [a, b] = [side[i], side[j]];
    if (Math.abs(a) <= tol && Math.abs(b) <= tol) {
      hits.push(corners[i], corners[j]);
      continue;
    }
    if (a * b > 0) continue;
    const t = a / (a - b);
    if (t < -1e-6 || t > 1 + 1e-6) continue;
    hits.push(add3(corners[i], mul3(sub3(corners[j], corners[i]), Math.min(1, Math.max(0, t)))));
  }
  const unique: Vec3[] = [];
  for (const p of hits) if (!unique.some((q) => len3(sub3(p, q)) <= tol)) unique.push(p);
  if (unique.length < 3) return [];
  const c = unique.reduce<Vec3>((s, p) => add3(s, p), [0, 0, 0]).map((v) => v / unique.length) as Vec3;
  const hint: Vec3 = Math.abs(normal[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0];
  const u = cross3(hint, normal);
  const ul = len3(u) || 1;
  const tangent: Vec3 = [u[0] / ul, u[1] / ul, u[2] / ul];
  const bitangent = cross3(normal, tangent);
  return unique
    .map((p) => ({ p, a: Math.atan2(dot3(sub3(p, c), bitangent), dot3(sub3(p, c), tangent)) }))
    .sort((p, q) => p.a - q.a)
    .map((p) => p.p);
}

/**
 * The plane clipped to `box`, or, when it misses, a quad on the plane centered on the box's projection so the
 * handle stays in view.
 */
export function planePolygon(origin: Vec3, normal: Vec3, box: Box): Vec3[] {
  const clipped = clipPlane(origin, normal, box);
  if (clipped.length >= 3) return clipped;
  const center: Vec3 = [0, 1, 2].map((k) => (box.min[k] + box.max[k]) / 2) as Vec3;
  const onto = add3(center, mul3(normal, -dot3(sub3(center, origin), normal)));
  const hint: Vec3 = Math.abs(normal[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0];
  const u0 = cross3(hint, normal);
  const ul = len3(u0) || 1;
  const u: Vec3 = [u0[0] / ul, u0[1] / ul, u0[2] / ul];
  const v = cross3(normal, u);
  const half = 0.5 * Math.max(box.max[0] - box.min[0], box.max[1] - box.min[1], box.max[2] - box.min[2], 1e-3);
  return [
    add3(onto, add3(mul3(u, half), mul3(v, half))),
    add3(onto, add3(mul3(u, -half), mul3(v, half))),
    add3(onto, add3(mul3(u, -half), mul3(v, -half))),
    add3(onto, add3(mul3(u, half), mul3(v, -half))),
  ];
}

/** `point` moved onto the nearest bearing from `from` that is a multiple of 45 degrees, keeping its projection. */
export function snap45(from: XY, point: XY): XY {
  const step: XY = [point[0] - from[0], point[1] - from[1]];
  const bearing = THREE.MathUtils.degToRad(Math.round(THREE.MathUtils.radToDeg(Math.atan2(step[0], step[1])) / 45) * 45);
  const dir: XY = [Math.sin(bearing), Math.cos(bearing)];
  const along = Math.max(dot2(step, dir), 0);
  return [from[0] + along * dir[0], from[1] + along * dir[1]];
}

export interface Ray {
  origin: Vec3;
  direction: Vec3;
}

/**
 * Ends of a quick cut from the rays under the two ends of the swept screen line: on the level plane through
 * `center` when the view looks down at least 20 degrees, else on the upright plane through `center` facing the
 * camera. Null when a ray misses its plane.
 */
export function pickCut(rays: [Ray, Ray], center: Vec3, forward: Vec3): [Vec3, Vec3] | null {
  const level = -forward[2] >= Math.sin(THREE.MathUtils.degToRad(LEVEL_PICK_DIP));
  const flat = Math.hypot(forward[0], forward[1]) || 1;
  const normal: Vec3 = level ? [0, 0, 1] : [forward[0] / flat, forward[1] / flat, 0];
  const hits = rays.map(({ origin, direction }) => {
    const along = normal[0] * direction[0] + normal[1] * direction[1] + normal[2] * direction[2];
    if (Math.abs(along) < 1e-9) return null;
    const t = ((center[0] - origin[0]) * normal[0] + (center[1] - origin[1]) * normal[1] + (center[2] - origin[2]) * normal[2]) / along;
    if (t <= 0) return null;
    return [0, 1, 2].map((k) => origin[k] + t * direction[k]) as Vec3;
  });
  return hits[0] && hits[1] ? [hits[0], hits[1]] : null;
}

/** Plan trace of the section's surface at elevation `z`, with its two slab edges, as polylines; a level slab (dip 0) has its polyline alone. */
export function traces(s: Section, z: number): [XY[], XY[], XY[]] {
  if (s.dip === 0) return [[s.segments[0].a, ...s.segments.map((g): XY => [g.a[0] + g.u[0] * g.length, g.a[1] + g.u[1] * g.length])], [], []];
  const d = THREE.MathUtils.degToRad(s.dip);
  const shift = (z - s.z) / Math.tan(d);
  const edge = s.half / Math.sin(d);
  const along = (offset: number): XY[] => {
    const out: XY[] = [];
    s.segments.forEach((g, j) => {
      const n: XY = [g.u[1], -g.u[0]];
      const at = (p: XY): XY => [p[0] + n[0] * offset, p[1] + n[1] * offset];
      const b: XY = [g.a[0] + g.u[0] * g.length, g.a[1] + g.u[1] * g.length];
      if (j === 0) out.push(at(g.a));
      if (j === s.segments.length - 1) out.push(at(b));
      else {
        // miter: the offset lines of this segment and the next meet on the bisector through the vertex
        const next = s.segments[j + 1].u;
        const m: XY = [n[0] + next[1], n[1] - next[0]];
        const k = 1 + dot2(n, [next[1], -next[0]]);
        out.push(k > 1e-6 ? [b[0] + (m[0] * offset) / k, b[1] + (m[1] * offset) / k] : at(b));
      }
    });
    return out;
  };
  return [along(-shift), along(-shift - edge), along(-shift + edge)];
}

/**
 * The section's plan bounds at the elevations of `box`, widened by the slab, or a level slab's elevations; null when it
 * misses the box.
 */
export function sectionBox(s: Section, box: Box): Box | null {
  if (s.dip === 0) {
    const [lo, hi] = [Math.max(box.min[2], s.z - s.half), Math.min(box.max[2], s.z + s.half)];
    return lo <= hi ? { min: [box.min[0], box.min[1], lo], max: [box.max[0], box.max[1], hi] } : null;
  }
  const xy = [box.min[2], box.max[2]].flatMap((z) => traces(s, z).flat());
  const min: Vec3 = [Math.max(box.min[0], Math.min(...xy.map((p) => p[0]))), Math.max(box.min[1], Math.min(...xy.map((p) => p[1]))), box.min[2]];
  const max: Vec3 = [Math.min(box.max[0], Math.max(...xy.map((p) => p[0]))), Math.min(box.max[1], Math.max(...xy.map((p) => p[1]))), box.max[2]];
  return min[0] <= max[0] && min[1] <= max[1] ? { min, max } : null;
}

/** Uniforms every material shares; the viewer writes its section into them before each frame. */
export const sectionUniforms = {
  uSecCount: { value: 0 },
  uSecHalf: { value: 0 },
  uSecUnfolded: { value: 0 },
  uSecSlab: { value: Array.from({ length: MAX_SEGMENTS }, () => new THREE.Vector4()) },
  uSecStart: { value: Array.from({ length: MAX_SEGMENTS }, () => new THREE.Vector4()) },
  uSecEnd: { value: Array.from({ length: MAX_SEGMENTS }, () => new THREE.Vector4()) },
  uSecMove: { value: Array.from({ length: MAX_SEGMENTS }, () => new THREE.Vector4()) },
};

export function writeSection(s: Section | null, unfolded: boolean): void {
  const u = sectionUniforms;
  u.uSecCount.value = s ? s.segments.length : 0;
  u.uSecHalf.value = s ? s.half : 0;
  u.uSecUnfolded.value = s && unfolded ? 1 : 0;
  s?.segments.forEach((g, j) => {
    u.uSecSlab.value[j].fromArray(g.slab);
    u.uSecStart.value[j].fromArray(g.start);
    u.uSecEnd.value[j].fromArray(g.end);
    u.uSecMove.value[j].fromArray(g.move);
  });
}

/** The GLSL mirror of `inSlab`, `segmentOf` and `unfold`, plus the inverse motion and the distance to a cut face. */
export const SECTION_GLSL = /* glsl */ `
uniform int uSecCount;
uniform float uSecHalf;
uniform float uSecUnfolded;
uniform vec4 uSecSlab[${MAX_SEGMENTS}];
uniform vec4 uSecStart[${MAX_SEGMENTS}];
uniform vec4 uSecEnd[${MAX_SEGMENTS}];
uniform vec4 uSecMove[${MAX_SEGMENTS}];
float secSide(vec4 q, vec3 p) { return dot(q.xyz, p) + q.w; }
bool secIn(int j, vec3 p) {
  return secSide(uSecStart[j], p) >= 0.0 && secSide(uSecEnd[j], p) >= 0.0 && abs(secSide(uSecSlab[j], p)) <= uSecHalf;
}
int secHolding(vec3 p) {
  for (int j = 0; j < ${MAX_SEGMENTS}; j++) {
    if (j >= uSecCount) break;
    if (secIn(j, p)) return j;
  }
  return -1;
}
bool sectionKeep(vec3 p) { return uSecCount == 0 || secHolding(p) >= 0; }
int secSegment(vec3 p) {
  for (int j = 0; j < ${MAX_SEGMENTS}; j++) {
    if (j >= uSecCount - 1 || secSide(uSecEnd[j], p) >= 0.0) return j;
  }
  return 0;
}
vec3 sectionPlace(vec3 p, vec3 ref) {
  if (uSecUnfolded < 0.5 || uSecCount == 0) return p;
  vec4 m = uSecMove[secSegment(ref)];
  return vec3(m.x * p.x + m.y * p.y + m.z, -m.y * p.x + m.x * p.y + m.w, p.z);
}
vec3 sectionTurn(vec3 v, vec3 ref) {
  if (uSecUnfolded < 0.5 || uSecCount == 0) return v;
  vec4 m = uSecMove[secSegment(ref)];
  return vec3(m.x * v.x + m.y * v.y, -m.y * v.x + m.x * v.y, v.z);
}
vec3 sectionUnplace(vec3 q, vec3 ref) {
  if (uSecUnfolded < 0.5 || uSecCount == 0) return q;
  vec4 m = uSecMove[secSegment(ref)];
  vec2 r = q.xy - m.zw;
  return vec3(m.x * r.x - m.y * r.y, m.y * r.x + m.x * r.y, q.z);
}
vec3 sectionEye(vec3 q) {
  if (!isOrthographic) return cameraPosition;
  vec3 back = vec3(viewMatrix[0][2], viewMatrix[1][2], viewMatrix[2][2]);
  return q + back * dot(cameraPosition - q, back);
}
float sectionEdge(vec3 p) {
  int j = secHolding(p);
  if (j < 0) return 1e30;
  float e = uSecHalf - abs(secSide(uSecSlab[j], p));
  if (j == 0) e = min(e, secSide(uSecStart[j], p));
  if (j == uSecCount - 1) e = min(e, secSide(uSecEnd[j], p));
  return e;
}
`;
