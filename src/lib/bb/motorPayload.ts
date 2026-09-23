/* ------------------------------------------------------------------ *
 * Översätter appens underlag till optimeringsmotorns dataformat.
 * Ingen beräkning sker här – bara omformning av redan inläst data.
 * ------------------------------------------------------------------ */

import type { Insats } from "./typer";
import type { Medarbetare } from "./vy";
import { ssgWindows, harHårt, forbudnaKunder, hårdaMotorvillkor, mjukaMotorvillkor, skillWindowsFromVillkor, workTimeWindowsFromVillkor, type MedarbetarVillkor } from "./villkor";
import { defaultTidstyp, expanderaAktiviteter, kunderUtanKontakt, type PlanAktivitet } from "./aktiviteter";
import {
  DEFAULT_WORK_TIME_MODEL_ID,
  STANDARD_WORK_TIME_MODELS,
  defaultWeeklyHours,
  ensureMinutesModel,
  type WorkTimeModel,
} from "./arbetstid";
import { harHärleddJour, jourMonsterFranSchema, jourNamnFranSchema } from "./nattJour";
import { MOTOR_MAX_INSATSER as MOTOR_OCCURRENCE_CEILING } from "./motorPeriod";

export type MotorPayload = Record<string, unknown>;

const KLOCKA = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Historiskt importvärde, inte ett uttryckligt nattmått (36 h 20 min = 2180 min). */
function arLegacyHeltid36_33(hours: number) {
  return Math.round(hours * 60) === 36 * 60 + 20;
}

function isoDag(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function veckodag(iso: string) {
  const d = new Date(iso + "T12:00:00Z");
  return ((d.getUTCDay() + 6) % 7) + 1; // 1 = måndag
}

function tid(v: unknown): string | null {
  const s = String(v ?? "").trim().replace(".", ":");
  const m = s.match(/^(\d{1,2}):(\d{2})/);
  if (!m) return null;
  const t = `${String(m[1] ?? "").padStart(2, "0")}:${m[2] ?? ""}`;
  return KLOCKA.test(t) ? t : null;
}

function plussa(t: string, minuter: number) {
  const delar = t.split(":").map(Number);
  const h = delar[0] ?? 0;
  const m = delar[1] ?? 0;
  const v = ((h * 60 + m + minuter) % 1440 + 1440) % 1440;
  return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
}

/** Gör en kompetens jämförbar: gemener, utan mellanslag. */
function normKompetens(v: unknown) {
  return String(v ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

export type Passmall = { id: string; type: string; start: string; end: string; breaks: { offset: number; minutes: number }[]; skills: string[] };

/** Standardmallar när verksamheten inte angett egna. Utan rast, så att inga
 *  insatser hamnar i ett obemannat rasthål (motorn kräver full täckning). */
export const STANDARDMALLAR: Passmall[] = [
  { id: "dag", type: "day", start: "07:00", end: "16:00", breaks: [], skills: [] },
  { id: "kvall", type: "evening", start: "13:30", end: "22:00", breaks: [], skills: [] },
  { id: "natt", type: "night", start: "21:00", end: "07:30", breaks: [], skills: [] },
];

/** Default motortak för insatstillfällen (occurrences). Motorn är auktoritativ via BB_MAX_OCCURRENCES eller data.limits.maxOccurrences. */
export const MOTOR_DEFAULT_MAX_OCCURRENCES = 1600;
/** Begärt tak i payload. Samma som motorns verifierade ceiling. */
export const MOTOR_REQUESTED_MAX_OCCURRENCES = MOTOR_OCCURRENCE_CEILING;
/** Begärt support-tak. Samma som motorns verifierade ceiling 250000. */
export const MOTOR_REQUESTED_MAX_SUPPORT_COMBINATIONS = 250000;
/** @deprecated Använd MOTOR_DEFAULT_MAX_OCCURRENCES. Klientvarning, inte motorns enda gräns. */
export const MOTOR_MAX_INSATSER = MOTOR_DEFAULT_MAX_OCCURRENCES;

function klockMin(t: string) {
  return Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
}

/** Ryms insatsen inom mallens arbetstid? */
function tacker(mall: Passmall, start: string, minuter: number) {
  if (mall.type === "jour") return false;
  const a = klockMin(mall.start);
  let b = klockMin(mall.end);
  if (b <= a) b += 1440;
  let s = klockMin(start);
  if (s < a) s += 1440;
  return s >= a && s + minuter <= b;
}

/** Passmallar ur det inlästa schemat – arbetspass och, separat, sovande jour. */
function mallarFranSchema(pass: { start: string; slut: string; jour?: boolean }[] | undefined) {
  const arbete = new Map<string, number>();
  const jourTid = new Map<string, number>();
  for (const p of pass || []) {
    const s = tid(p.start);
    const e = tid(p.slut);
    if (!s || !e || s === e) continue;
    let langd = klockMin(e) - klockMin(s);
    if (langd <= 0) langd += 1440;
    if (langd < 180 || langd > 900) continue;
    const nyckel = `${s}-${e}`;
    if (p.jour) jourTid.set(nyckel, (jourTid.get(nyckel) || 0) + 1);
    else arbete.set(nyckel, (arbete.get(nyckel) || 0) + 1);
  }
  const arbetsmallar = [...arbete.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([nyckel], i) => {
      const [s, e] = nyckel.split("-");
      return { id: `p${i + 1}`, type: typAvStart(String(s)), start: String(s), end: String(e), breaks: [], skills: [] } as Passmall;
    });
  const jourmallar = [...jourTid.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([nyckel], i) => {
      const [s, e] = nyckel.split("-");
      return { id: i === 0 ? "jour" : `jour${i + 1}`, type: "jour", start: String(s), end: String(e), breaks: [], skills: [] } as Passmall;
    });
  return [...arbetsmallar, ...jourmallar];
}

/** Kompletterar mallarna så att varje insats ryms i minst ett pass. */
function tackandeMallar(basMallar: Passmall[], insatser: { start: string; minuter: number }[]) {
  const mallar = basMallar.slice(0, 12);
  const utan: { start: string; minuter: number }[] = [];
  for (const i of insatser) {
    if (mallar.some((m) => tacker(m, i.start, i.minuter))) continue;
    utan.push(i);
  }
  const grupper = new Map<string, number>();
  for (const i of utan) {
    const s = klockMin(i.start);
    const nyckel = `${String(Math.floor(s / 60)).padStart(2, "0")}:${s % 60 >= 30 ? "30" : "00"}`;
    grupper.set(nyckel, Math.max(grupper.get(nyckel) || 0, i.minuter));
  }
  let nr = 0;
  for (const [start, minuter] of [...grupper.entries()].sort()) {
    if (mallar.length >= 12) break;
    if (mallar.some((m) => tacker(m, start, minuter))) continue;
    const langd = Math.max(480, minuter + 60);
    mallar.push({ id: `t${++nr}`, type: typAvStart(start), start, end: plussa(start, langd), breaks: [], skills: [] });
  }
  return mallar;
}

/** Kortare varianter av passmallarna, så att pass kan kortas och läggas om
 *  efter hur behoven ligger. Motorn väljer bara de pass som behövs. */
function kortareVarianter(mallar: Passmall[]): Passmall[] {
  const ut = mallar.slice(0, 12);
  const finns = (start: string, slut: string) => ut.some((m) => m.start === start && m.end === slut);
  for (const m of mallar.slice(0, 4)) {
    if (ut.length >= 12) break;
    if (m.type === "jour") continue;
    const a = klockMin(m.start);
    let b = klockMin(m.end);
    if (b <= a) b += 1440;
    const langd = b - a;
    if (langd <= 360) continue;
    const slut = plussa(m.start, 360);
    if (finns(m.start, slut)) continue;
    ut.push({ id: `k${ut.length + 1}`, type: m.type, start: m.start, end: slut, breaks: [], skills: [] });
  }
  return ut;
}


function profilerFor(m: Medarbetare, mallar: Passmall[]) {
  const idFor = (typ: string) => mallar.filter((t) => t.type === typ).map((t) => t.id);
  const dag = idFor("day");
  const kvall = idFor("evening");
  const natt = idFor("night");
  const jour = idFor("jour");
  const p = String(m.passprofil || "").toLowerCase();
    const nattOk = m.nattbehorig === true;
    const jourOk = m.jour === true;
  let ut: string[] = [];
  if (/natt|jour/.test(p) && !/dag|kväll|kvall/.test(p)) ut = [...(nattOk ? natt : []), ...(jourOk ? jour : [])];
  else if (/kväll|kvall/.test(p)) ut = kvall;
  else if (/dag/.test(p)) ut = dag;
  else ut = [...dag, ...kvall, ...(nattOk ? natt : []), ...(jourOk ? jour : [])];
  const rensad = ut.filter(Boolean);
  return rensad.length ? rensad : mallar.filter((t) => t.type !== "jour").slice(0, 1).map((t) => t.id);
}

const JOUR_DEFAULT = { start: "23:00", end: "06:30", weekdays: [1, 2, 3, 4, 5, 6, 7] as number[] };

function jourMall(regler: MotorRegler): Passmall {
  const j = regler.jour ?? JOUR_DEFAULT;
  return { id: "jour", type: "jour", start: j.start || "23:00", end: j.end || "06:30", breaks: [], skills: [] };
}

function laggJourMall(mallar: Passmall[], regler: MotorRegler): Passmall[] {
  const mall = jourMall(regler);
  if (mallar.some((m) => m.type === "jour")) return mallar;
  if (mallar.length < 12) return [...mallar, mall];
  const kort = mallar.findIndex((m) => m.id.startsWith("k"));
  if (kort >= 0) {
    const ut = mallar.slice();
    ut[kort] = mall;
    return ut;
  }
  return [...mallar.slice(0, 11), mall];
}

/** Passtyp ur starttid: dag före 11, kväll 11–17, annars natt. */
function typAvStart(start: string) {
  const h = Number(start.slice(0, 2)) || 0;
  if (h < 11) return "day";
  if (h < 17) return "evening";
  return "night";
}

export type MotorRegler = {
  minRestHours: number;
  fullTimeWeeklyHours: number;
  maxWeeklyHours: number;
  maxShiftHours: number;
  maxConsecutiveDays: number;
  nightFloor: number;
  jourFloor: number;
  flexibilityStep: number;
  minWeeklyRestHours?: number;
  withinPassMinutesPerShift?: number;
  minRestDaysInFourWeeks?: number;
  minGeneratedShiftMinutes?: number;
  preferredMinShiftMinutes?: number;
  jour?: { start: string; end: string; weekdays: number[] };
  shiftProfiles?: Record<string, Record<string, unknown>>;
};

export type PayloadResultat = {
  payload: MotorPayload;
  info: {
    from: string;
    to: string;
    dagar: number;
    insatser: number;
    kunder: number;
    medarbetare: number;
    vikarier: number;
    openShifts: number;
    syntheticEmployees: number;
    overTak: boolean;
    maxInsatser: number;
    occurrenceLimitDefault?: number;
    occurrenceLimitRequest?: number;
    occurrenceLimitAuthority?: "motor";
    occurrenceLimitNote?: string;
    regler: MotorRegler;
  };
  /** motorns employeeId → namn och vikariemärkning */
  medarbetarKarta: Record<string, { namn: string; vikarie: boolean }>;
  /** motorns interventionId → appens insatsrad */
  insatsKarta: Record<string, { radId: string; kund: string; insats: string; start: string }>;
  varningar: string[];
};

/** Bygger motorns underlag ur appens insatser och personal. */
export function byggMotorPayload(opts: {
  rader: Insats[];
  medarbetare: Medarbetare[];
  from: string;
  dagar: number;
  timkostnad: number;
  /** Bakåtkompatibel workplace-fallback. Används inte som allas mått. */
  heltidVecka?: number;
  /** Redigerad visningskolumn per namn; blir override bara om den skiljer sig från default. */
  heltidPerNamn?: Record<string, number>;
  regler?: Partial<MotorRegler>;
  /** Pass ur det inlästa schemat – används som låsta pass runt periodens gränser. */
  schemaPass?: {
    namn: string;
    datum: string;
    start: string;
    slut: string;
    jour?: boolean;
    vakant?: boolean;
    rad?: string;
    kod?: string;
  }[];
  mallar?: Passmall[];
  revision?: number;
  objectiveWeights?: { continuitySek: number; spreadSekPerPermille: number; uncoveredSekPerMinute?: number };
  planAktiviteter?: PlanAktivitet[];
  kontaktpersoner?: Record<string, string>;
  planningMode?: "optimizeExisting" | "generateFromNeeds";
}): PayloadResultat {
  const varningar: string[] = [];
  const dagar = Math.max(1, Math.min(42, Math.round(opts.dagar || 7)));
  const from = opts.from;
  const to = isoDag(from, dagar - 1);
  const planningMode = opts.planningMode === "generateFromNeeds" ? "generateFromNeeds" : "optimizeExisting";
  const egnaMallar = opts.mallar && opts.mallar.length ? opts.mallar : mallarFranSchema(opts.schemaPass);
  const basMallar = (planningMode === "generateFromNeeds"
    ? egnaMallar
    : egnaMallar.length
      ? egnaMallar
      : STANDARDMALLAR
  ).slice(0, 12);

  const regler: MotorRegler = {
    minRestHours: 11,
    fullTimeWeeklyHours: Math.max(1, Math.min(60, opts.heltidVecka || defaultWeeklyHours())),
    maxWeeklyHours: 48,
    maxShiftHours: 12,
    maxConsecutiveDays: 5,
    nightFloor: 0,
    jourFloor: 0,
    flexibilityStep: 15,
    minWeeklyRestHours: 36,
    withinPassMinutesPerShift: 0,
    minRestDaysInFourWeeks: 9,
    minGeneratedShiftMinutes: 0,
    preferredMinShiftMinutes: 240,
    jour: {
      start: opts.regler?.jour?.start || "23:00",
      end: opts.regler?.jour?.end || "06:30",
      weekdays: opts.regler?.jour?.weekdays?.length ? opts.regler.jour.weekdays : [1, 2, 3, 4, 5, 6, 7],
    },
    shiftProfiles: {
      combinedWorkJour: {
        maxSpanHours: 19,
        minJourMinutesInNightWindow: 300,
        nightWindowStart: "22:00",
        nightWindowEnd: "08:00",
        requiredRestMode: "at_least_duty_length",
        compensatoryRestEqualToSpan: true,
        compensatoryMustFollowImmediately: true,
        requiresException: false,
      },
      COMBINED_WORK_JOUR: {
        maxSpanHours: 19,
        minJourMinutesInNightWindow: 300,
        requiredRestMode: "at_least_duty_length",
        requiresException: false,
      },
      extendedCombinedWorkJour: {
        maxSpanHours: 24,
        minJourMinutesInNightWindow: 300,
        nightWindowStart: "22:00",
        nightWindowEnd: "08:00",
        requiredRestMode: "at_least_duty_length",
        compensatoryRestEqualToSpan: true,
        compensatoryMustFollowImmediately: true,
        requiresException: true,
      },
      longException: {
        maxSpanHours: 24,
        minJourMinutesInNightWindow: 300,
        requiredRestMode: "at_least_duty_length",
        requiresException: true,
      },
    },
    ...(opts.regler || {}),
  };
  regler.jour = {
    start: regler.jour?.start || "23:00",
    end: regler.jour?.end || "06:30",
    weekdays: regler.jour?.weekdays?.length ? regler.jour.weekdays : [1, 2, 3, 4, 5, 6, 7],
  };
  const explicitJourFloor = Boolean(opts.regler && Object.prototype.hasOwnProperty.call(opts.regler, "jourFloor"));
  const jourMonster = jourMonsterFranSchema(opts.schemaPass, from, dagar);
  if (!explicitJourFloor) regler.jourFloor = jourMonster.jourFloor;
  if (jourMonster.medJo > 0) {
    regler.jour = {
      start: jourMonster.start,
      end: jourMonster.end,
      weekdays: regler.jour.weekdays,
    };
  }
  let perPassMin = 0;
  for (const a of opts.planAktiviteter || []) {
    if (!a.aktiv || a.frekvens !== "per_pass" || defaultTidstyp(a) !== "inom_pass") continue;
    perPassMin += a.enhet === "timmar" ? a.omfattning * 60 : a.omfattning;
  }
  regler.withinPassMinutesPerShift = Math.max(0, Math.min(180, Math.round(perPassMin)));
  if (regler.minWeeklyRestHours == null) regler.minWeeklyRestHours = 36;
  if (!Number.isFinite(Number(regler.minRestDaysInFourWeeks)) || Number(regler.minRestDaysInFourWeeks) < 1) {
    if (opts.regler && Object.prototype.hasOwnProperty.call(opts.regler, "minRestDaysInFourWeeks") && Number(opts.regler.minRestDaysInFourWeeks) === 0) {
      varningar.push("F-01 kan inte stängas av. minRestDaysInFourWeeks 0 tolkas som 9.");
    }
    regler.minRestDaysInFourWeeks = 9;
  }
  const mallTimmar = (t: Passmall) => {
    const a = klockMin(t.start);
    let b = klockMin(t.end);
    if (b <= a) b += 1440;
    return (b - a) / 60;
  };


  const kundNr = new Map<string, number>();
  const customers: Record<string, unknown>[] = [];
  const kundId = (namn: string) => {
    const nyckel = String(namn || "Gemensamt");
    if (!kundNr.has(nyckel)) {
      const nr = kundNr.size + 1;
      kundNr.set(nyckel, nr);
      customers.push({ id: `k${nr}`, code: `Kund ${nr}`, name: nyckel, active: true });
    }
    return `k${kundNr.get(nyckel)}`;
  };

  /** Kompetenskrav ur insatsradens yrkesgruppskolumner. */
  const kravFor = (r: Insats) => {
    const nycklar = Object.keys(r);
    const hitta = (m: RegExp) => {
      const k = nycklar.find((n) => m.test(n.toLowerCase()));
      return k ? String(r[k] ?? "").trim() : "";
    };
    const delegerat = hitta(/delegerat/);
    if (delegerat && !/^(ingen|-|nej)/i.test(delegerat)) return [normKompetens(delegerat)];
    const yrke = hitta(/yrkesgrupp/);
    if (yrke && !/^ingen/i.test(yrke)) return [normKompetens(yrke)];
    return [];
  };

  const interventions: Record<string, unknown>[] = [];
  const insatsKarta: PayloadResultat["insatsKarta"] = {};
  const kravSet = new Set<string>();
  let hoppade = 0;
  let klippta = 0;
  for (const r of opts.rader) {
    const datum = String(r.datum || "").slice(0, 10);
    if (!datum || datum < from || datum > to) continue;
    const start = tid(r.start);
    let minuter = Math.round(Number(r.minuter) || 0);
    if (!start || minuter < 1) {
      hoppade++;
      continue;
    }
    if (minuter > 480) {
      minuter = 480;
      klippta++;
    }
    const flyttbar = Boolean(r.flyttbar);
    const fonster = tid(r.fonsterSlut) || tid(r.slut);
    const fonsterLangre = Boolean(fonster && fonster > plussa(start, minuter));
    const flexibel = flyttbar && fonster && fonsterLangre;
    const latestEnd = flexibel && fonster ? fonster : plussa(start, minuter);
    const id = `i${interventions.length + 1}`;
    const skills = kravFor(r);
    for (const s of skills) kravSet.add(s);
    interventions.push({
      id,
      customerId: kundId(String(r.kund || "Gemensamt")),
      name: String(r.insats || "Insats"),
      type: flexibel ? "flexible" : "fixed",
      minutes: minuter,
      doubleStaff: Boolean(r.tvaPersoner),
      weekdays: [veckodag(datum)],
      skills,
      date: datum,
      start,
      latestEnd,
    });
    insatsKarta[id] = {
      radId: String(r["id"] ?? r._id ?? r.kallrad ?? id),
      kund: String(r.kund || "Gemensamt"),
      insats: String(r.insats || "Insats"),
      start,
    };
  }
  if (hoppade) varningar.push(`${hoppade} insatsrader kunde inte tolkas och togs inte med.`);
  if (klippta) varningar.push(`${klippta} insatser var längre än 8 timmar och kortades till 8 timmar i beräkningen.`);

  // Motorn kräver att varje insats ryms i ett arbetspass. Passmallarna
  // kompletteras därför utifrån insatsernas tider, och de insatser som ändå
  // inte kan bemannas lyfts ut med en tydlig varning i stället för att hela
  // beräkningen ska falla.
  const jourFranSchema = basMallar.filter((m) => m.type === "jour");
  const arbeteBas = basMallar.filter((m) => m.type !== "jour");
  const mallarArbete = planningMode === "generateFromNeeds"
    ? arbeteBas.slice(0, 12)
    : kortareVarianter(
        tackandeMallar(
          arbeteBas,
          interventions.map((i) => ({ start: String(i["start"]), minuter: Number(i["minutes"]) })),
        ),
      ).filter((m) => m.type !== "jour");
  const mallar = jourFranSchema.length
    ? [...mallarArbete.slice(0, Math.max(0, 12 - jourFranSchema.length)), ...jourFranSchema]
    : mallarArbete.slice(0, 12);
  const otackta: string[] = [];
  const tacktaInsatser = planningMode === "generateFromNeeds"
    ? interventions.slice()
    : interventions.filter((i) => {
        const ok = mallar.some((m) => tacker(m, String(i["start"]), Number(i["minutes"])));
        if (!ok) {
          otackta.push(String(i["start"]));
          delete insatsKarta[String(i["id"])];
        }
        return ok;
      });
  if (otackta.length) {
    const tider = [...new Set(otackta)].sort().slice(0, 6).join(", ");
    varningar.push(
      `${otackta.length} insatser ryms inte i något arbetspass (tider: ${tider}) och togs inte med i beräkningen. Lägg till en passmall som täcker de tiderna.`,
    );
  }
  interventions.length = 0;
  interventions.push(...tacktaInsatser);

  // Passmallarna måste rymmas i den röda passgränsen, annars avvisar motorn dem.
  const langsta = mallar.length ? Math.max(...mallar.map(mallTimmar)) : 0;
  if (langsta > regler.maxShiftHours) {
    regler.maxShiftHours = Math.min(16, Math.ceil(langsta));
    varningar.push(
      `En passmall är ${langsta.toFixed(1)} timmar lång, längre än den röda gränsen. Gränsen höjdes till ${regler.maxShiftHours} timmar för den här beräkningen.`,
    );
  }

  const overTak = interventions.length > MOTOR_MAX_INSATSER;
  if (!interventions.length) varningar.push("Inga insatser i den valda perioden.");

  // Vaken natt kräver betald täckning 22–06. Om mallarna inte räcker ska
  // kravet ändå skickas oförändrat – motorn redovisar brist, inte ett sänkt golv.
  const nattTackt = (minut: number) =>
    mallar.some((m) => {
      if (m.type === "jour") return false;
      const a = klockMin(m.start);
      let b = klockMin(m.end);
      if (b <= a) b += 1440;
      const t = minut < a ? minut + 1440 : minut;
      return t >= a && t < b;
    });
  let helaNatten = true;
  for (let m = 22 * 60; m < 30 * 60; m += 30) if (!nattTackt(m % 1440)) helaNatten = false;
  if (regler.nightFloor > 0 && !helaNatten) {
    varningar.push(
      "Inget arbetspass täcker hela natten. Kravet på vaken natt skickas oförändrat; sovande jour täcker det inte.",
    );
  }
  const joNamn = jourNamnFranSchema(opts.schemaPass);
  const nagonJour = opts.medarbetare.some((m) => harHärleddJour(m.jour, m.namn, joNamn) && !harHårt(((m as Medarbetare).villkor || []) as MedarbetarVillkor[], "ingen_jour", from, to));
  if (regler.jourFloor > 0 || nagonJour) {
    const medJour = laggJourMall(mallar.slice(), regler);
    mallar.length = 0;
    mallar.push(...medJour);
  }

  const medarbetarKarta: PayloadResultat["medarbetarKarta"] = {};
  let workTimeModels: WorkTimeModel[] = STANDARD_WORK_TIME_MODELS.map((m) => ({ ...m }));
  const defaultWorkTimeModelId = DEFAULT_WORK_TIME_MODEL_ID;
  let ordinarie = 0;
  let vikarieNr = 0;
  let tempNr = 0;
  /** Ingen placerad / vakant rad är inte en person. Explicit namngiven vikarie (vakant: false) får vara employee. */
  const personalKalla = opts.medarbetare.filter((m) => !m.vakant).slice(0, 80);
  const employees = personalKalla.map((m, i) => {
    const id = `e${i + 1}`;
    const tillfallig = m.resourceType === "temporary";
    const arVikarie = Boolean(m.vikarie) && !tillfallig;
    const code = tillfallig ? `T${++tempNr}` : arVikarie ? `V${++vikarieNr}` : `M${++ordinarie}`;
    medarbetarKarta[id] = { namn: m.namn, vikarie: arVikarie };
    const skills = new Set<string>();
    if (m.delegering === true) skills.add("delegering");
    if (m.samordnare) skills.add("samordnare");
    if (!tillfallig) {
      skills.add("undersköterska".toLowerCase());
      // Alla kompetenskrav som finns i underlaget måste kunna mötas av personal
      // som har delegering; utan delegeringskrav kan alla ta insatsen.
      for (const k of kravSet) if (m.delegering === true || !/delegerin|sjuksk/.test(k)) skills.add(k);
    }
    for (const k of m.kompetenser || []) {
      const n = String(k || "").trim().toLowerCase();
      if (n) skills.add(n);
    }
    const farTillsattas = (m as { vikarieFarTillsattas?: boolean }).vikarieFarTillsattas;
    const villkor = ((m as Medarbetare).villkor || []) as MedarbetarVillkor[];
    const night = m.nattbehorig === true && !harHårt(villkor, "ingen_natt", from, to) && !harHårt(villkor, "endast_dag", from, to) && !harHårt(villkor, "endast_kvall", from, to);
    const jourOk = tillfallig
      ? m.jour === true && !harHårt(villkor, "ingen_jour", from, to)
      : harHärleddJour(m.jour, m.namn, joNamn) && !harHårt(villkor, "ingen_jour", from, to);
    const hard = hårdaMotorvillkor(m, from, to, kundId, i);
    const soft = tillfallig ? {} : mjukaMotorvillkor(villkor, from, to, kundId);
    const datedSkills = tillfallig ? [] : skillWindowsFromVillkor(villkor, from, to);
    const windows = tillfallig ? [] : workTimeWindowsFromVillkor(villkor, from, to);
    let workTimeModelId = tillfallig ? undefined : (String(m.workTimeModelId || "").trim() || undefined);
    const visadHeltid = opts.heltidPerNamn?.[m.namn];
    // Legacyimport satte 36,33 på alla rader. Det är inte ett valt nattmått.
    if (!tillfallig && !workTimeModelId && Number.isFinite(visadHeltid) && Number(visadHeltid) > 0 && !arLegacyHeltid36_33(Number(visadHeltid))) {
      const minutes = Math.round(Number(visadHeltid) * 60);
      const ensured = ensureMinutesModel(minutes, workTimeModels);
      workTimeModels = ensured.models;
      if (ensured.id !== defaultWorkTimeModelId) workTimeModelId = ensured.id;
    }
    const ssg = tillfallig
      ? Math.max(0, Math.min(100, Number(m.grad) || 0))
      : Math.max(0, Math.min(100, Number(m.grad) || 100));
    return {
      id,
      code,
      name: m.namn,
      resourceType: m.resourceType === "temp_pool" ? "temp_pool" : tillfallig ? "temporary" : "employee",
      ssg,
      ssgWindows: tillfallig ? [] : ssgWindows(Number(m.grad) || 100, villkor, from, to),
      ...(workTimeModelId ? { workTimeModelId } : {}),
      ...(windows.length ? { workTimeWindows: windows } : {}),
      night,
      jour: jourOk,
      status: arVikarie && farTillsattas === false ? "inactive" : "active",
      profiles: profilerFor({ ...m, jour: jourOk, nattbehorig: night }, mallar),
      hourlyCost: tillfallig
        ? (Number(m.timkostnad) > 0 ? Number(m.timkostnad) : 0)
        : Number(m.timkostnad) > 0 ? Number(m.timkostnad) : null,
      skills: [...skills],
      skillWindows: datedSkills,
      constraints: {
        hard,
        ...(Object.keys(soft).length ? { soft } : {}),
      },
    };
  });
  if (!employees.length) varningar.push("Ingen personal är inläst – motorn kan inte lägga pass.");

  const namnTillEid: Record<string, string> = {};
  for (const [id, m] of Object.entries(medarbetarKarta)) namnTillEid[m.namn] = id;
  const expanderade = expanderaAktiviteter({
    aktiviteter: opts.planAktiviteter || [],
    fran: from,
    till: to,
    arbetspass: (opts.schemaPass || []).filter((p) => !p.jour).length,
    kunder: [...kundNr.keys()].filter((n) => !/^gemensam/i.test(n)),
    kontaktpersoner: opts.kontaktpersoner || {},
    sekoiaRader: opts.rader,
  });
  for (const a of expanderade) {
    if (a.tidstyp !== "separat_tid") continue;
    let kvar = Math.round(a.timmar * 60);
    if (kvar < 1) continue;
    const cid = kundId(a.kund || "Gemensamt");
    const krav = a.medarbetare ? namnTillEid[a.medarbetare] : undefined;
    let n = 0;
    while (kvar > 0) {
      const minuter = Math.min(480, kvar);
      kvar -= minuter;
      n += 1;
      const id = `p${interventions.length + 1}`;
      interventions.push({
        id,
        customerId: cid,
        name: a.namn,
        type: "flexible",
        minutes: minuter,
        doubleStaff: false,
        weekdays: [1, 2, 3, 4, 5, 6, 7],
        skills: [],
        date: from,
        start: "09:00",
        latestEnd: "17:00",
        ...(krav ? { requiredEmployeeId: krav } : {}),
      });
      insatsKarta[id] = { radId: `${a.typ}-${a.kund || "gemensam"}-${n}`, kund: a.kund || "Gemensamt", insats: a.namn, start: "09:00" };
    }
  }

  const nattpersonal = employees.filter((e) => e.status === "active" && e.night).length;
  const jourpersonal = employees.filter((e) => e.status === "active" && Boolean((e as { jour?: boolean }).jour)).length;
  if (regler.nightFloor > nattpersonal) {
    varningar.push(
      nattpersonal < 1
        ? "Ingen medarbetare är nattbehörig, men kravet på vaken natt skickas oförändrat."
        : `Bara ${nattpersonal} medarbetare är nattbehöriga mot kravet ${regler.nightFloor}. Kravet sänks inte.`,
    );
  }
  if (regler.jourFloor > jourpersonal) {
    varningar.push(
      jourpersonal < 1
        ? "Ingen medarbetare är jourbehörig, men kravet på sovande jour skickas oförändrat."
        : `Bara ${jourpersonal} medarbetare är jourbehöriga mot kravet ${regler.jourFloor}. Kravet sänks inte.`,
    );
  }

  // Frånvaro ur medarbetarvyns fält. Motorn hanterar hela dagar.
  const absences: Record<string, unknown>[] = [];
  personalKalla.forEach((m, i) => {
    const kod = String(m.franvaro || "ingen");
    if (kod === "ingen" || !kod) return;
    const id = `e${i + 1}`;
    if (kod === "semester") {
      absences.push({ id: `a${absences.length + 1}`, employeeId: id, start: from, end: to });
      return;
    }
    if (kod === "ledig1v") {
      absences.push({ id: `a${absences.length + 1}`, employeeId: id, start: from, end: isoDag(from, Math.min(6, dagar - 1)) });
      return;
    }
    if (kod === "arbetar2v") {
      // Arbetar två veckor per månad: frånvarande övriga veckor.
      for (let d = 14; d < dagar; d += 28) {
        absences.push({
          id: `a${absences.length + 1}`,
          employeeId: id,
          start: isoDag(from, d),
          end: isoDag(from, Math.min(d + 13, dagar - 1)),
        });
      }
      return;
    }
    const m1 = kod.match(/(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})/);
    if (m1) absences.push({ id: `a${absences.length + 1}`, employeeId: id, start: m1[1], end: m1[2] });
  });

  // Låsta pass upp till 27 dagar före och efter, så F-01 kan räkna rullande 28-dagar.
  // Sovande jour, natt och betalda pass ingår. workDayDate räknas i motorn.
  const namnTillId = new Map<string, string>();
  personalKalla.forEach((m, i) => namnTillId.set(m.namn, `e${i + 1}`));
  const gransFore = isoDag(from, -27);
  const gransEfter = isoDag(to, 27);
  const boundaryShifts: Record<string, unknown>[] = [];
  for (const p of opts.schemaPass || []) {
    const datum = String(p.datum || "").slice(0, 10);
    const utanfor = (datum >= gransFore && datum < from) || (datum > to && datum <= gransEfter);
    if (!utanfor) continue;
    const id = namnTillId.get(p.namn);
    const start = tid(p.start);
    const slut = tid(p.slut);
    if (!id || !start || !slut) continue;
    let langd = Number(slut.slice(0, 2)) * 60 + Number(slut.slice(3, 5)) - (Number(start.slice(0, 2)) * 60 + Number(start.slice(3, 5)));
    if (langd <= 0) langd += 1440;
    boundaryShifts.push({
      id: `b${boundaryShifts.length + 1}`,
      employeeId: id,
      date: datum,
      start,
      end: slut,
      type: p.jour ? "jour" : typAvStart(start),
      skills: p.jour ? [] : [],
      breaks: !p.jour && langd >= 360 ? [{ offset: 240, minutes: 30 }] : [],
    });
  }

  const vacantShifts: Record<string, unknown>[] = [];
  for (const p of opts.schemaPass || []) {
    if (!p.vakant) continue;
    const datum = String(p.datum || "").slice(0, 10);
    if (datum < from || datum > to) continue;
    const start = tid(p.start);
    const slut = tid(p.slut);
    if (!start || !slut) continue;
    vacantShifts.push({
      id: `open${vacantShifts.length + 1}`,
      date: datum,
      start,
      end: slut,
      type: p.jour ? "jour" : typAvStart(start),
      kod: p.kod || (p.jour ? "Jo" : "Ar"),
      rowLabel: p.rad || p.namn,
      source: "medvind",
      origin: "fore",
    });
  }

  const schemaDatum = (opts.schemaPass || []).map((p) => String(p.datum || "").slice(0, 10)).filter((d) => d >= gransFore && d <= gransEfter);
  const boundaryKnownFrom = [from, ...schemaDatum].sort()[0];
  const boundaryKnownTo = [to, ...schemaDatum].sort().at(-1);

  const kundSkill = (cid: string) => `kund:${cid}`;
  for (const i of interventions) {
    const cid = String(i["customerId"] || "");
    const sk = Array.isArray(i["skills"]) ? (i["skills"] as string[]).slice() : [];
    if (cid && !sk.includes(kundSkill(cid))) sk.push(kundSkill(cid));
    i["skills"] = sk;
  }
  const forbudPerNamn = new Map<string, string[]>();
  for (const m of personalKalla) {
    forbudPerNamn.set(m.namn, forbudnaKunder(((m as Medarbetare).villkor || []) as MedarbetarVillkor[], from, to));
  }
  for (const e of employees) {
    const forbud = forbudPerNamn.get(String(e.name)) || [];
    for (const [kundNamn, nr] of kundNr) {
      if (forbud.includes(kundNamn)) continue;
      const sk = kundSkill(`k${nr}`);
      if (!e.skills.includes(sk)) e.skills.push(sk);
    }
  }

  const saknarKontakt = kunderUtanKontakt(
    [...kundNr.keys()].filter((n) => !/^gemensam/i.test(n)),
    opts.kontaktpersoner || {},
    opts.planAktiviteter || [],
  );
  if (saknarKontakt.length) {
    varningar.push(
      `${saknarKontakt.length} kund${saknarKontakt.length > 1 ? "er" : ""} saknar kontaktperson medan en kontaktpersonsaktivitet är aktiv.`,
    );
  }

  const payload: MotorPayload = {
    schemaVersion: 1,
    inputRevision: Math.max(1, Math.round(opts.revision || 1)),
    workplace: {
      id: "vh1",
      name: "Verksamheten",
      timezone: "Europe/Stockholm",
      start: from,
      end: to,
      workTimeModels,
      defaultWorkTimeModelId,
    },
    customers,
    employees,
    vacantShifts,
    openShifts: vacantShifts,
    interventions,
    templates: mallar,
    absences,
    boundaryShifts,
    boundaryAcknowledged: true,
    boundaryKnownFrom,
    boundaryKnownTo,
    planningMode,
    ...(planningMode === "generateFromNeeds" ? { existingSchedule: null } : {}),
    rules: regler,
    compensatoryRest: [],
    economy: { hourlyCost: Math.max(0, Number(opts.timkostnad) || 270) },
    limits: {
      maxOccurrences: MOTOR_REQUESTED_MAX_OCCURRENCES,
      maxSupportCombinations: MOTOR_REQUESTED_MAX_SUPPORT_COMBINATIONS,
    },
    objectiveWeights: {
      continuitySek: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.continuitySek ?? 50))),
      spreadSekPerPermille: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.spreadSekPerPermille ?? 2.5))),
      uncoveredSekPerMinute: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.uncoveredSekPerMinute ?? 500))),
      nightSeries3Sek: 30,
      nightSeries4Sek: 90,
    },
  };

  return {
    payload,
    info: {
      from,
      to,
      dagar,
      insatser: interventions.length,
      overTak,
      maxInsatser: MOTOR_DEFAULT_MAX_OCCURRENCES,
      occurrenceLimitDefault: MOTOR_DEFAULT_MAX_OCCURRENCES,
      occurrenceLimitRequest: MOTOR_REQUESTED_MAX_OCCURRENCES,
      occurrenceLimitAuthority: "motor",
      occurrenceLimitNote:
        "overTak jämför mot default 1600. Motorns faktiska tak sätts av data.limits.maxOccurrences (begärt 4000) eller BB_MAX_OCCURRENCES.",
      kunder: customers.length,
      medarbetare: employees.length,
      vikarier: vikarieNr,
      openShifts: vacantShifts.length,
      syntheticEmployees: 0,
      regler,
    },
    medarbetarKarta,
    insatsKarta,
    varningar,
  };
}
