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

export function workTimeWindowsFromVillkor(villkor: MedarbetarVillkor[], fran: string, till: string) {
  return villkor
    .filter((v) => v.typ === "arbetstid" && gallerIPeriod(v, fran, till))
    .map((v) => {
      const modelId = String(v.payload?.["modelId"] || "").trim();
      const weeklyMinutes = Number(v.payload?.["weeklyMinutes"]);
      return {
        start: v.from && v.from > fran ? v.from : fran,
        end: v.till && v.till < till ? v.till : till,
        ...(modelId ? { modelId } : {}),
        ...(Number.isFinite(weeklyMinutes) && weeklyMinutes > 0 ? { weeklyMinutes } : {}),
      };
    })
    .filter((w) => w.modelId || w.weeklyMinutes != null);
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

export function kunderMedStyrka(villkor: MedarbetarVillkor[], typ: string, styrka: VillkorsStyrka, fran: string, till: string) {
  return villkor
    .filter((v) => v.typ === typ && v.styrka === styrka && gallerIPeriod(v, fran, till))
    .map((v) => String(v.payload?.["kund"] || "").trim())
    .filter(Boolean);
}

export function helgLage(helg: string): "all" | "none" | "every_other" | "every_third" {
  const v = String(helg || "").toLowerCase();
  if (v === "inga" || v === "inga helger") return "none";
  if (v === "vartredje" || v === "var tredje helg") return "every_third";
  if (v === "alla" || v === "varje helg" || v === "varje") return "all";
  if (v === "varannan" || v === "varannan helg") return "every_other";
  return "all";
}

export function skillWindowsFromVillkor(villkor: MedarbetarVillkor[], fran: string, till: string) {
  return villkor
    .filter((v) => (v.typ === "kompetens" || v.typ === "delegering") && gallerIPeriod(v, fran, till))
    .map((v) => ({
      skill: String(v.payload?.["skill"] || (v.typ === "delegering" ? "delegering" : "")).trim(),
      start: v.from && v.from > fran ? v.from : fran,
      end: v.till && v.till < till ? v.till : till,
    }))
    .filter((w) => w.skill);
}

function tal(v: MedarbetarVillkor, key: string) {
  const n = Number(v.payload?.[key]);
  return Number.isFinite(n) ? n : undefined;
}

/** Hårda motorvillkor ur personfält och datumstyrda villkor. Önskemål hamnar inte här. */
export function hårdaMotorvillkor(
  m: {
    passprofil?: string;
    helg?: string;
    tidigastStart?: string;
    senastSlut?: string;
    maxDagarIFoljd?: number;
    villkor?: MedarbetarVillkor[];
    resourceType?: string;
    tillgangligaDatum?: string[];
    jour?: boolean | null;
    nattbehorig?: boolean | null;
    maxTimmar?: number | null;
  },
  fran: string,
  till: string,
  kundId: (namn: string) => string,
  offset = 0,
) {
  const villkor = m.villkor || [];
  const hard: Record<string, unknown> = {};
  const p = String(m.passprofil || "").toLowerCase();
  if (harHårt(villkor, "endast_dag", fran, till) || (/dag/.test(p) && !/kväll|kvall|natt/.test(p))) hard.allowedTypes = ["day"];
  else if (harHårt(villkor, "endast_kvall", fran, till) || /kväll|kvall/.test(p)) hard.allowedTypes = ["evening"];
  else if (harHårt(villkor, "endast_natt", fran, till) || /natt|jour/.test(p)) hard.allowedTypes = ["night", "jour"];
  if (harHårt(villkor, "endast_vardag", fran, till)) hard.weekdays = [1, 2, 3, 4, 5];
  if (harHårt(villkor, "endast_helg", fran, till)) hard.weekdays = [6, 7];
  const lage = helgLage(m.helg || "");
  hard.weekendMode = lage;
  if (lage === "every_other" || lage === "every_third") hard.weekendOffset = offset;
  const tidig = String(m.tidigastStart || "").trim();
  const sen = String(m.senastSlut || "").trim();
  if (/^\d{1,2}:\d{2}$/.test(tidig)) hard.earliestStart = tidig.length === 4 ? `0${tidig}` : tidig;
  if (/^\d{1,2}:\d{2}$/.test(sen)) hard.latestEnd = sen.length === 4 ? `0${sen}` : sen;
  for (const v of villkor) {
    if (v.styrka !== "maste" || !gallerIPeriod(v, fran, till)) continue;
    if (v.typ === "max_pass" && tal(v, "timmar") != null) hard.maxShiftHours = tal(v, "timmar");
    if (v.typ === "min_pass" && tal(v, "timmar") != null) hard.minShiftHours = tal(v, "timmar");
    if (v.typ === "max_natt_foljd" && tal(v, "dagar") != null) hard.maxNightConsecutive = Math.round(tal(v, "dagar")!);
    if (v.typ === "max_jour_foljd" && tal(v, "dagar") != null) hard.maxJourConsecutive = Math.round(tal(v, "dagar")!);
    if (v.typ === "min_ledighet" && tal(v, "dagar") != null) hard.minConsecutiveOffDays = Math.round(tal(v, "dagar")!);
    if (v.typ === "max_dagar_foljd" && tal(v, "dagar") != null) hard.maxConsecutiveDays = Math.round(tal(v, "dagar")!);
  }
  const forbud = forbudnaKunder(villkor, fran, till).map(kundId);
  if (forbud.length) hard.forbiddenCustomerIds = forbud;
  const maste = kunderMedStyrka(villkor, "kundmaste", "maste", fran, till).map(kundId);
  if (maste.length) hard.requiredCustomerIds = maste;
  if (m.resourceType === "temporary") {
    const datum = Array.isArray(m.tillgangligaDatum) ? m.tillgangligaDatum.filter(Boolean) : [];
    hard.dates = datum;
    const helgIDatum = datum.some((d) => {
      const wd = new Date(`${d}T12:00:00Z`).getUTCDay();
      return wd === 0 || wd === 6;
    });
    hard.weekendMode = helgIDatum ? "all" : "none";
    delete hard.weekendOffset;
    if (m.jour === true && m.nattbehorig !== true && !String(m.tidigastStart || "").trim() && !String(m.senastSlut || "").trim()) {
      hard.allowedTypes = ["jour"];
    }
    if (m.maxTimmar != null && Number.isFinite(Number(m.maxTimmar)) && Number(m.maxTimmar) >= 0) {
      hard.maxPaidMinutes = Math.round(Number(m.maxTimmar) * 60);
    }
  }
  return hard;
}

export function mjukaMotorvillkor(villkor: MedarbetarVillkor[], fran: string, till: string, kundId: (namn: string) => string) {
  const soft: Record<string, unknown> = {};
  const types: string[] = [];
  if (villkor.some((v) => v.typ === "endast_dag" && v.styrka === "onskemal" && gallerIPeriod(v, fran, till))) types.push("day");
  if (villkor.some((v) => v.typ === "endast_kvall" && v.styrka === "onskemal" && gallerIPeriod(v, fran, till))) types.push("evening");
  if (villkor.some((v) => v.typ === "endast_natt" && v.styrka === "onskemal" && gallerIPeriod(v, fran, till))) types.push("night");
  if (types.length) soft.preferredTypes = types;
  const bor = kunderMedStyrka(villkor, "kundbor", "onskemal", fran, till).map(kundId);
  const masteOnskemal = kunderMedStyrka(villkor, "kundmaste", "onskemal", fran, till).map(kundId);
  const pref = [...bor, ...masteOnskemal];
  if (pref.length) soft.preferredCustomerIds = pref;
  const minLedig = villkor.find((v) => v.typ === "min_ledighet" && v.styrka === "onskemal" && gallerIPeriod(v, fran, till));
  if (minLedig && tal(minLedig, "dagar") != null) soft.minConsecutiveOffDays = Math.round(tal(minLedig, "dagar")!);
  const maxFoljd = villkor.find((v) => v.typ === "max_dagar_foljd" && v.styrka === "onskemal" && gallerIPeriod(v, fran, till));
  if (maxFoljd && tal(maxFoljd, "dagar") != null) soft.maxConsecutiveDays = Math.round(tal(maxFoljd, "dagar")!);
  return soft;
}
