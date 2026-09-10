/** Datumstyrda individuella villkor. Generell modell, ingen personhårdkodning. */

export type VillkorsStyrka = "maste" | "onskemal";

export type MedarbetarVillkor = {
  id: string;
  typ: string;
  styrka: VillkorsStyrka;
  from?: string;
  till?: string;
  aktiv: boolean;
  payload?: Record<string, unknown>;
};

export function gallerIPeriod(v: MedarbetarVillkor, fran: string, till: string) {
  if (!v.aktiv) return false;
  if (v.till && v.till < fran) return false;
  if (v.from && v.from > till) return false;
  return true;
}

export function ssgForDag(basSsg: number, villkor: MedarbetarVillkor[], dag: string) {
  let ssg = basSsg;
  for (const v of villkor) {
    if (v.typ !== "ssg" || !v.aktiv) continue;
    if (v.from && dag < v.from) continue;
    if (v.till && dag > v.till) continue;
    const n = Number(v.payload?.["ssg"]);
    if (Number.isFinite(n)) ssg = n;
  }
  return ssg;
}

export function ssgWindows(basSsg: number, villkor: MedarbetarVillkor[], fran: string, till: string) {
  const ssgVillkor = villkor.filter((v) => v.typ === "ssg" && gallerIPeriod(v, fran, till));
  if (!ssgVillkor.length) return [] as { start: string; end: string; ssg: number }[];
  return ssgVillkor.map((v) => ({
    start: v.from && v.from > fran ? v.from : fran,
    end: v.till && v.till < till ? v.till : till,
    ssg: Number(v.payload?.["ssg"]) || basSsg,
  }));
}

export function harHårt(villkor: MedarbetarVillkor[], typ: string, fran: string, till: string) {
  return villkor.some((v) => v.typ === typ && v.styrka === "maste" && gallerIPeriod(v, fran, till));
}

export function forbudnaKunder(villkor: MedarbetarVillkor[], fran: string, till: string) {
  return villkor
    .filter((v) => v.typ === "kundforbud" && v.styrka === "maste" && gallerIPeriod(v, fran, till))
    .map((v) => String(v.payload?.["kund"] || "").trim())
    .filter(Boolean);
}
