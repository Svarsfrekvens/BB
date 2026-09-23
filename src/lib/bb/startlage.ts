/** Sessionens första vy. Ingen datamodell – bara UX-läge i webbläsaren. */

export type Startlage = "start" | "upload" | "app";

const NYCKEL = "bb.startlage";
const lyssnare = new Set<() => void>();

function las(): Startlage {
  if (typeof sessionStorage === "undefined") return "start";
  const v = sessionStorage.getItem(NYCKEL);
  if (v === "upload" || v === "app" || v === "start") return v;
  return "start";
}

let lage: Startlage = las();

export function hamtaStartlage(): Startlage {
  return lage;
}

export function sattStartlage(nasta: Startlage) {
  lage = nasta;
  try {
    sessionStorage.setItem(NYCKEL, nasta);
  } catch {
    /* privat läge */
  }
  lyssnare.forEach((f) => f());
}

export function lyssnaStartlage(f: () => void) {
  lyssnare.add(f);
  return () => lyssnare.delete(f);
}
