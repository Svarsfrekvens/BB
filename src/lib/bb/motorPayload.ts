/* ------------------------------------------------------------------ *
 * Översätter appens underlag till optimeringsmotorns dataformat.
 * Ingen beräkning sker här – bara omformning av redan inläst data.
 * ------------------------------------------------------------------ */

import type { Insats } from "./typer";
import type { Medarbetare } from "./vy";
import { expanderaAktiviteter, kunderUtanKontakt, type PlanAktivitet } from "./aktiviteter";
import { ssgWindows, harHårt, forbudnaKunder, type MedarbetarVillkor } from "./villkor";

export type MotorPayload = Record<string, unknown>;

const KLOCKA = /^([01]\d|2[0-3]):[0-5]\d$/;

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

/** Motorns tak för antal insatstillfällen (samma värde som domain.py). */
export const MOTOR_MAX_INSATSER = 1600;

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

/** Passmallar ur det inlästa schemat – verksamhetens verkliga pass. */
function mallarFranSchema(pass: { start: string; slut: string; jour?: boolean }[] | undefined) {
  const antal = new Map<string, number>();
  for (const p of pass || []) {
    if (p.jour) continue;
    const s = tid(p.start);
    const e = tid(p.slut);
    if (!s || !e || s === e) continue;
    let langd = klockMin(e) - klockMin(s);
    if (langd <= 0) langd += 1440;
    if (langd < 180 || langd > 900) continue;
    const nyckel = `${s}-${e}`;
    antal.set(nyckel, (antal.get(nyckel) || 0) + 1);
  }
  return [...antal.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([nyckel], i) => {
      const [s, e] = nyckel.split("-");
      return { id: `p${i + 1}`, type: typAvStart(String(s)), start: String(s), end: String(e), breaks: [], skills: [] } as Passmall;
    });
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
  const nattOk = Boolean(m.nattbehorig || m.jour);
  let ut: string[] = [];
  if (/natt|jour/.test(p)) ut = nattOk ? natt : kvall;
  else if (/kväll|kvall/.test(p)) ut = nattOk ? [...kvall, ...natt] : kvall;
  else if (/dag/.test(p)) ut = nattOk ? [...dag, ...natt] : dag;
  else ut = nattOk ? [...dag, ...kvall, ...natt] : [...dag, ...kvall];
  if (nattOk) ut = [...ut, ...jour];
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
  jour?: { start: string; end: string; weekdays: number[] };
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
    overTak: boolean;
    maxInsatser: number;
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
  heltidVecka?: number;
  regler?: Partial<MotorRegler>;
  /** Pass ur det inlästa schemat – används som låsta pass runt periodens gränser. */
  schemaPass?: { namn: string; datum: string; start: string; slut: string; jour?: boolean }[];
  mallar?: Passmall[];
  revision?: number;
  objectiveWeights?: { continuitySek: number; spreadSekPerPermille: number; uncoveredSekPerMinute?: number };
  planAktiviteter?: PlanAktivitet[];
  kontaktpersoner?: Record<string, string>;
}): PayloadResultat {
  const varningar: string[] = [];
  const dagar = Math.max(1, Math.min(42, Math.round(opts.dagar || 7)));
  const from = opts.from;
  const to = isoDag(from, dagar - 1);
  const egnaMallar = opts.mallar && opts.mallar.length ? opts.mallar : mallarFranSchema(opts.schemaPass);
  const basMallar = (egnaMallar.length ? egnaMallar : STANDARDMALLAR).slice(0, 12);

  const regler: MotorRegler = {
    minRestHours: 11,
    fullTimeWeeklyHours: Math.max(1, Math.min(60, opts.heltidVecka || 36.33)),
    maxWeeklyHours: 48,
    maxShiftHours: 12,
    maxConsecutiveDays: 5,
    nightFloor: 1,
    jourFloor: 0,
    flexibilityStep: 15,
    jour: {
      start: opts.regler?.jour?.start || "23:00",
      end: opts.regler?.jour?.end || "06:30",
      weekdays: opts.regler?.jour?.weekdays?.length ? opts.regler.jour.weekdays : [1, 2, 3, 4, 5, 6, 7],
    },
    ...(opts.regler || {}),
  };
  regler.jour = {
    start: regler.jour?.start || "23:00",
    end: regler.jour?.end || "06:30",
    weekdays: regler.jour?.weekdays?.length ? regler.jour.weekdays : [1, 2, 3, 4, 5, 6, 7],
  };
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
  const mallar = kortareVarianter(
    tackandeMallar(
      basMallar,
      interventions.map((i) => ({ start: String(i["start"]), minuter: Number(i["minutes"]) })),
    ),
  );
  const otackta: string[] = [];
  const tacktaInsatser = interventions.filter((i) => {
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

  // Vaken natt kräver att ett arbetspass täcker hela natten (22–06). I
  // verksamheter där natten sköts av sovande jour finns inget sådant pass.
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
    regler.nightFloor = 0;
    regler.jourFloor = Math.max(1, regler.jourFloor || 0);
    varningar.push(
      "Inget arbetspass täcker hela natten – nätterna sköts av sovande jour. Kravet på vaken natt ingår därför inte i den här beräkningen.",
    );
  }
  if (regler.jourFloor > 0) {
    const medJour = laggJourMall(mallar, regler);
    mallar.length = 0;
    mallar.push(...medJour);
  }

  const medarbetarKarta: PayloadResultat["medarbetarKarta"] = {};
  let ordinarie = 0;
  let vikarieNr = 0;
  const employees = opts.medarbetare.slice(0, 80).map((m, i) => {
    const id = `e${i + 1}`;
    const arVikarie = Boolean(m.vikarie || m.vakant);
    const code = arVikarie ? `V${++vikarieNr}` : `M${++ordinarie}`;
    medarbetarKarta[id] = { namn: m.namn, vikarie: arVikarie };
    const skills = new Set<string>();
    if (m.delegering) skills.add("delegering");
    if (m.samordnare) skills.add("samordnare");
    skills.add("undersköterska".toLowerCase());
    // Alla kompetenskrav som finns i underlaget måste kunna mötas av personal
    // som har delegering; utan delegeringskrav kan alla ta insatsen.
    for (const k of kravSet) if (m.delegering || !/delegerin|sjuksk/.test(k)) skills.add(k);
    const farTillsattas = (m as { vikarieFarTillsattas?: boolean }).vikarieFarTillsattas;
    const villkor = ((m as Medarbetare).villkor || []) as MedarbetarVillkor[];
    const night = Boolean(m.nattbehorig || m.jour) && !harHårt(villkor, "ingen_natt", from, to) && !harHårt(villkor, "endast_dag", from, to);
    const jourOk = Boolean(m.jour) && !harHårt(villkor, "ingen_jour", from, to);
    return {
      id,
      code,
      name: m.namn,
      ssg: Math.max(0, Math.min(100, Number(m.grad) || 100)),
      ssgWindows: ssgWindows(Number(m.grad) || 100, villkor, from, to),
      night,
      status: arVikarie && farTillsattas === false ? "inactive" : "active",
      profiles: profilerFor({ ...m, jour: jourOk, nattbehorig: night }, mallar),
      hourlyCost: Number(m.timkostnad) > 0 ? Number(m.timkostnad) : null,
      skills: [...skills],
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

  // Motorn måste kunna bemanna varje insats. Ordinarie sysselsättningsgrader
  // räcker sällan till full täckning, så beräkningen får tillgång till några
  // extra vikariepass. De används bara om de behövs, eftersom kostnaden vägs in.
  if (employees.length && interventions.length) {
    const behovTimmar = interventions.reduce((s, i) => s + Number(i["minutes"]), 0) / 60;
    const takTimmar = employees
      .filter((e) => e.status === "active")
      .reduce((s, e) => s + (e.ssg / 100) * regler.fullTimeWeeklyHours * (dagar / 7), 0);
    const onskat = behovTimmar * 3.5;
    const perExtra = regler.fullTimeWeeklyHours * (dagar / 7);
    const extra = Math.max(0, Math.min(8, Math.ceil((onskat - takTimmar) / Math.max(1, perExtra))));
    const forlaga = employees[0]!;
    for (let k = 0; k < extra; k++) {
      const id = `x${k + 1}`;
      medarbetarKarta[id] = { namn: `Extra vikarie ${k + 1}`, vikarie: true };
      employees.push({
        ...forlaga,
        id,
        code: `V${++vikarieNr}`,
        name: `Extra vikarie ${k + 1}`,
        ssg: 100,
        ssgWindows: [],
        status: "active",
        hourlyCost: opts.timkostnad > 0 ? opts.timkostnad : null,
      });
    }
    if (extra)
      varningar.push(
        `Beräkningen fick tillgång till ${extra} extra vikariepass, eftersom ordinarie sysselsättningsgrader inte räcker för att täcka alla insatser. Bara de pass som verkligen behövs används.`,
      );
  }

  // Kravet på vaken natt / sovande jour kan aldrig bli högre än nattbehöriga.
  const nattpersonal = employees.filter((e) => e.status === "active" && e.night).length;
  if (regler.nightFloor > nattpersonal) {
    if (nattpersonal < 1)
      varningar.push("Ingen medarbetare är nattbehörig, så kravet på vaken natt kunde inte tillämpas i beräkningen.");
    else varningar.push(`Kravet på vaken natt sänktes till ${nattpersonal} eftersom bara så många är nattbehöriga.`);
    regler.nightFloor = nattpersonal;
  }
  if (regler.jourFloor > nattpersonal) {
    if (nattpersonal < 1)
      varningar.push("Ingen medarbetare är nattbehörig, så kravet på sovande jour kunde inte tillämpas i beräkningen.");
    else varningar.push(`Kravet på sovande jour sänktes till ${nattpersonal} eftersom bara så många är nattbehöriga.`);
    regler.jourFloor = nattpersonal;
  }

  // Frånvaro ur medarbetarvyns fält. Motorn hanterar hela dagar.
  const absences: Record<string, unknown>[] = [];
  opts.medarbetare.slice(0, 80).forEach((m, i) => {
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

  // Låsta pass: de sista två dagarna före perioden och de första två efter,
  // så att dygnsvilan över periodgränsen respekteras. Sovande jour skickas inte.
  const namnTillId = new Map<string, string>();
  opts.medarbetare.slice(0, 80).forEach((m, i) => namnTillId.set(m.namn, `e${i + 1}`));
  const gransFore = isoDag(from, -2);
  const gransEfter = isoDag(to, 2);
  const boundaryShifts: Record<string, unknown>[] = [];
  for (const p of opts.schemaPass || []) {
    const datum = String(p.datum || "").slice(0, 10);
    const utanfor = (datum >= gransFore && datum < from) || (datum > to && datum <= gransEfter);
    if (!utanfor || p.jour) continue;
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
      type: typAvStart(start),
      skills: [],
      breaks: langd >= 360 ? [{ offset: 240, minutes: 30 }] : [],
    });
  }

  const kundSkill = (cid: string) => `kund:${cid}`;
  for (const i of interventions) {
    const cid = String(i["customerId"] || "");
    const sk = Array.isArray(i["skills"]) ? (i["skills"] as string[]).slice() : [];
    if (cid && !sk.includes(kundSkill(cid))) sk.push(kundSkill(cid));
    i["skills"] = sk;
  }
  const forbudPerNamn = new Map<string, string[]>();
  for (const m of opts.medarbetare.slice(0, 80)) {
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
    workplace: { id: "vh1", name: "Verksamheten", timezone: "Europe/Stockholm", start: from, end: to },
    customers,
    employees,
    interventions,
    templates: mallar,
    absences,
    boundaryShifts,
    boundaryAcknowledged: true,
    rules: regler,
    economy: { hourlyCost: Math.max(0, Number(opts.timkostnad) || 270) },
    objectiveWeights: {
      continuitySek: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.continuitySek ?? 50))),
      spreadSekPerPermille: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.spreadSekPerPermille ?? 2.5))),
      uncoveredSekPerMinute: Math.max(0, Math.min(10000, Number(opts.objectiveWeights?.uncoveredSekPerMinute ?? 500))),
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
      maxInsatser: MOTOR_MAX_INSATSER,
      kunder: customers.length,
      medarbetare: employees.length,
      vikarier: vikarieNr,
      regler,
    },
    medarbetarKarta,
    insatsKarta,
    varningar,
  };
}
