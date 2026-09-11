/* ------------------------------------------------------------------ *
 * Ny modell: nuvarande schema + kundbehov (Sekoia) + regler → bättre schema.
 *
 *   schemaOriginal (orörd)   sekoiaOriginal (orörd)
 *           \                  /
 *            analysera()  →  FÖRE
 *                  |
 *            optimeraInsatser()   (enkel, flyttar inom fönstret)
 *                  |
 *            analysera()  →  EFTER (förslag)
 *                  |
 *            jamfor()  →  Före & efter
 *
 * Ingen automatisk regelmotor. Appen räknar, jämför och föreslår – den
 * garanterar inte ett färdigt lagligt schema. Steg B (schemaläggningen) är
 * medvetet lämnad som en tydlig gräns så en riktig motor kan kopplas in.
 * ------------------------------------------------------------------ */

import * as C from "./core";
import type { DatumPass } from "./medvind";
import { beraknaKpi, rymInomPass } from "./kpi";

export type Slot = { datum: string; klockan: string; behov: number; dimensionerat: number; bemanning: number; jour: number };

export type Lage = {
  fran: string;
  till: string;
  dagar: number;
  schematidH: number;
  jourH: number;
  kundbehovH: number;
  personalbehovH: number;
  /** Schemalagd kundnära arbetstid (bemannade insatser + kundnära aktiviteter). */
  kundnaraH: number;
  /** Kundnära tid % = kundnaraH ÷ schematidH. */
  kundnaraPct: number;
  /** Täckt behov % = bemannat kundbehov ÷ totalt kundbehov. */
  tackningPct: number;
  ejKundnaraH: number;
  bemannatKundbehovH: number;
  /** totalt kundbehov − bemannat kundbehov. Aldrig större än totalt kundbehov. */
  obemannatKundbehovH: number;
  /** Samtidighets-/nattgolvskurvan, kan vara större än rått kundbehov. */
  dimensionerandeResursbehovH: number;
  /** Gap mellan dimensionerande resursbehov och faktisk bemanning. */
  otacktDimensionerandeResursH: number;
  kostnad: number;
  obemannadeIntervall: number;
  /** Alias för otacktDimensionerandeResursH (historiskt fältnamn). */
  obemannatH: number;
  overkapacitetH: number;
  modellFel: boolean;
  inomPassOverflowH: number;
  /** Hur stor del av det dimensionerande behovet som är bemannat, i procent. */
  matchningPct: number;
  /** Beräknad intäkt: antal kunder × dygnsersättning × antal dygn. */
  intakt: number;
  /** Intäkt minus personalkostnad. */
  resultat: number;
  toppBehov: number;
  slots: Slot[];
  perTimme: { timme: number; behov: number; bemanning: number }[];
};


export type Flytt = { id: string; kund: string; insats: string; datum: string; fran: string; till: string; minuter: number };

/* ---------- Hjälp ---------- */

const min2slot = (m: number) => Math.floor(m / 30);
function klockMin(c: unknown) {
  const m = String(c ?? "").match(/(\d{1,2}):(\d{2})/);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}
function klocka(m: number) {
  const x = ((Math.round(m) % 1440) + 1440) % 1440;
  return `${String(Math.floor(x / 60)).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`;
}
function dagar(fran: string, till: string) {
  const ut: string[] = [];
  for (const d = new Date(fran + "T00:00:00Z"); d.toISOString().slice(0, 10) <= till; d.setUTCDate(d.getUTCDate() + 1)) {
    ut.push(d.toISOString().slice(0, 10));
  }
  return ut;
}

/** Bemanning per 30-minutersintervall ur det riktiga schemat. */
export function bemanningPerSlot(pass: DatumPass[], lista: string[]) {
  const idx = new Map(lista.map((d, i) => [d, i]));
  const aktiv = new Array(lista.length * 48).fill(0);
  const jour = new Array(lista.length * 48).fill(0);
  for (const p of pass) {
    const di = idx.get(p.datum);
    if (di == null) continue;
    const s = klockMin(p.start);
    let e = klockMin(p.slut);
    if (s == null || e == null) continue;
    if (e <= s) e += 1440;
    for (let sl = min2slot(s); sl < Math.ceil(e / 30); sl++) {
      const d2 = di + (sl >= 48 ? 1 : 0);
      if (d2 >= lista.length) continue;
      const cell = d2 * 48 + (sl % 48);
      if (p.jour) jour[cell] += 1;
      else aktiv[cell] += 1;
    }
  }
  return { aktiv, jour };
}

/** Ett läge: schemat mot behovet. Använder resurskurvan i core.ts oförändrad. */
export function analysera(opts: {
  rader: any[];
  pass: DatumPass[];
  fran: string;
  till: string;
  timkostnad: number;
  /** Timkostnad per medarbetare (default används när personen saknas). */
  timkostnadFor?: (namn: string) => number;
  /** Antal kunder och kronor per kund och dygn – ger beräknad intäkt. */
  antalKunder?: number;
  dygnsErsattning?: number;
  /** Kundnära tid som ryms i redan schemalagda pass (tidstyp inom_pass). Ökar inte schematid. */
  extraInomPassKundnaraH?: number;
  extraInomPassEjKundnaraH?: number;
}): Lage {
  const { rader, pass, fran, till, timkostnad } = opts;
  const lista = dagar(fran, till);
  const kurva = C.resurskurva(rader, fran, till);
  const { aktiv, jour } = bemanningPerSlot(pass, lista);
  const n = C.nyckeltal(rader);

  const slots: Slot[] = [];
  let obemannadeIntervall = 0;
  let obemannatH = 0;
  let overkapacitetH = 0;
  let bemannatKundbehovH = 0;
  let toppBehov = 0;
  let dimH = 0;
  const timBehov = new Array(24).fill(0);
  const timBem = new Array(24).fill(0);

  kurva.intervall.forEach((iv: any, i: number) => {
    const bem = aktiv[i] || 0;
    const jo = jour[i] || 0;
    slots.push({ datum: iv.datum, klockan: iv.klockan, behov: iv.rabehov, dimensionerat: iv.dimensionerat, bemanning: bem, jour: jo });
    dimH += iv.dimensionerat * 0.5;
    bemannatKundbehovH += Math.min(iv.rabehov, bem) * 0.5;
    if (iv.dimensionerat > bem + 1e-9) {
      obemannadeIntervall += 1;
      obemannatH += (iv.dimensionerat - bem) * 0.5;
    }
    if (bem > iv.rabehov) overkapacitetH += (bem - iv.rabehov) * 0.5;
    if (iv.rabehov > toppBehov) toppBehov = iv.rabehov;
    const t = Number(iv.klockan.slice(0, 2));
    timBehov[t] += iv.rabehov;
    timBem[t] += bem;
  });

  const arbetspass = pass.filter((p) => !p.jour);
  const schematidH = arbetspass.reduce((s, p) => s + p.timmar, 0);
  const jourH = pass.filter((p) => p.jour).reduce((s, p) => s + p.timmar, 0);
  const rymd = rymInomPass({
    schematidH,
    direktKundnaraH: bemannatKundbehovH,
    inomPassKundnaraH: opts.extraInomPassKundnaraH || 0,
    inomPassEjKundnaraH: opts.extraInomPassEjKundnaraH || 0,
  });
  const kpiRaw = beraknaKpi({
    schematidH,
    kundnaraArbetstidH: rymd.kundnaraH,
    totaltKundbehovH: n.kundbehovH,
    bemannatKundbehovH,
  });
  const kpi = { ...kpiRaw, modellFel: kpiRaw.modellFel || rymd.platsBrist };
  const kostnad = arbetspass.reduce((s, p) => s + p.timmar * (opts.timkostnadFor ? opts.timkostnadFor(p.namn) : timkostnad), 0);
  const intakt = (opts.antalKunder || 0) * (opts.dygnsErsattning || 0) * lista.length;
  const delare = lista.length * 2; // två intervall per timme och dag
  return {
    fran,
    till,
    dagar: lista.length,
    schematidH,
    jourH,
    kundbehovH: n.kundbehovH,
    personalbehovH: n.personalbehovH,
    kundnaraH: kpi.kundnaraH,
    kundnaraPct: kpi.kundnaraPct,
    tackningPct: kpi.tacktBehovPct,
    ejKundnaraH: kpi.ejKundnaraH,
    bemannatKundbehovH: kpi.bemannatKundbehovH,
    obemannatKundbehovH: kpi.obemannatKundbehovH,
    dimensionerandeResursbehovH: dimH,
    otacktDimensionerandeResursH: obemannatH,
    kostnad,
    obemannadeIntervall,
    obemannatH,
    overkapacitetH,
    modellFel: kpi.modellFel,
    inomPassOverflowH: rymd.overflowH,
    matchningPct: dimH > 0 ? Math.max(0, (1 - obemannatH / dimH)) * 100 : 100,
    intakt,
    resultat: intakt - kostnad,
    toppBehov,
    slots,
    perTimme: timBehov.map((b, t) => ({ timme: t, behov: b / delare, bemanning: timBem[t] / delare })),
  };
}

/* ---------- Vikariepass: pröva om de behövs ---------- */

export type VikarieBeslut = { id: string; namn: string; datum: string; start: string; slut: string; timmar: number; behovs: boolean };

/**
 * Prövar varje vikariepass mot det dimensionerande behovet. Täcker den ordinarie
 * personalen redan behovet under passet tas vikariepasset bort – annars fyller
 * det ett verkligt gap och behålls. Regelbaserat, inget behov av en motor.
 */
export function provaVikariepass(pass: DatumPass[], dimensionerat: number[], lista: string[]) {
  const idx = new Map(lista.map((d, i) => [d, i]));
  const { aktiv } = bemanningPerSlot(pass, lista);
  const celler = (p: DatumPass) => {
    const di = idx.get(p.datum);
    const s = klockMin(p.start);
    let e = klockMin(p.slut);
    if (di == null || s == null || e == null) return [];
    if (e <= s) e += 1440;
    const ut: number[] = [];
    for (let sl = min2slot(s); sl < Math.ceil(e / 30); sl++) {
      const d2 = di + (sl >= 48 ? 1 : 0);
      if (d2 >= lista.length) continue;
      ut.push(d2 * 48 + (sl % 48));
    }
    return ut;
  };

  const beslut: VikarieBeslut[] = [];
  const borttagna = new Set<string>();
  // Kortaste passen prövas först – de gör minst nytta om de behålls i onödan.
  const vikariepass = pass.filter((p) => p.vikarie && !p.jour).slice().sort((a, b) => a.timmar - b.timmar);
  for (const p of vikariepass) {
    const c = celler(p);
    const behovs = c.some((cell) => (aktiv[cell] || 0) - 1 < (dimensionerat[cell] || 0) - 1e-9);
    if (!behovs) for (const cell of c) aktiv[cell] = (aktiv[cell] || 0) - 1;
    if (!behovs) borttagna.add(p.id);
    beslut.push({ id: p.id, namn: p.namn, datum: p.datum, start: p.start, slut: p.slut, timmar: p.timmar, behovs });
  }
  return {
    beslut,
    borttagna: [...borttagna],
    antalBorttagna: borttagna.size,
    antalBehalls: beslut.length - borttagna.size,
  };
}


/* ---------- Steg A: fördela om de flyttbara insatserna ---------- */

/**
 * Fasta insatser ligger kvar. Flyttbara insatser prövas i 15-minutersteg inom
 * sitt egna tillåtna fönster och läggs där samtidigheten är lägst. Enkel och
 * regelbaserad – ingen optimeringsmotor.
 */
export function optimeraInsatser(rader: any[], fran: string, till: string, bemanning?: number[]) {
  const lista = dagar(fran, till);
  const idx = new Map(lista.map((d, i) => [d, i]));
  const last = new Float64Array(lista.length * 48);
  const kopior = rader.map((r) => ({ ...r }));

  const spann = (r: any) => {
    const s = klockMin(r.start);
    const dur = Math.max(1, Number(r.minuter) || 0);
    return { s, dur, personer: r.tvaPersoner ? 2 : 1 };
  };
  const lagg = (r: any, startMin: number, tecken: number) => {
    const di = idx.get(r.datum);
    if (di == null) return;
    const { dur, personer } = spann(r);
    for (let sl = min2slot(startMin); sl < Math.ceil((startMin + dur) / 30); sl++) {
      const d2 = di + (sl >= 48 ? 1 : 0);
      if (d2 >= lista.length) continue;
      last[d2 * 48 + (sl % 48)] = (last[d2 * 48 + (sl % 48)] || 0) + tecken * personer;
    }
  };
  /** Kostnad för att lägga insatsen med denna starttid: brist på personal väger
   *  tyngst, därefter samtidighet, sist avståndet från ursprungstiden. */
  const kostnadFor = (r: any, startMin: number) => {
    const di = idx.get(r.datum);
    if (di == null) return Infinity;
    const { dur, personer } = spann(r);
    let topp = 0;
    let brist = 0;
    for (let sl = min2slot(startMin); sl < Math.ceil((startMin + dur) / 30); sl++) {
      const d2 = di + (sl >= 48 ? 1 : 0);
      if (d2 >= lista.length) continue;
      const cell = d2 * 48 + (sl % 48);
      const nu = (last[cell] || 0) + personer;
      topp = Math.max(topp, nu);
      if (bemanning) brist = Math.max(brist, nu - (bemanning[cell] || 0));
    }
    return Math.max(0, brist) * 100000 + topp * 1000;
  };

  const flyttbara: any[] = [];
  for (const r of kopior) {
    const s = klockMin(r.start);
    if (s == null || !idx.has(r.datum)) continue;
    if (r.flyttbar && r.fonsterSlut) flyttbara.push(r);
    else lagg(r, s, +1);
  }
  // Längsta insats först – den har minst utrymme att välja på.
  flyttbara.sort((a, b) => (Number(b.minuter) || 0) - (Number(a.minuter) || 0));

  const flyttade: Flytt[] = [];
  for (const r of flyttbara) {
    const s0 = klockMin(r.fonsterStart ?? r.start)!;
    let sSlut = klockMin(r.fonsterSlut)!;
    if (sSlut <= s0) sSlut += 1440;
    const dur = Math.max(1, Number(r.minuter) || 0);
    const senast = Math.max(s0, sSlut - dur);
    let bast = klockMin(r.start)!;
    let bastVarde = Infinity;
    for (let start = s0; start <= senast; start += 15) {
      const v = kostnadFor(r, start) + Math.abs(start - klockMin(r.start)!) / 60;
      if (v < bastVarde) {
        bastVarde = v;
        bast = start;
      }
    }
    const gammal = r.start;
    if (r.fonsterStart == null) r.fonsterStart = gammal;
    if (klocka(bast) !== gammal) {
      r.start = klocka(bast);
      r.slut = klocka(bast + dur);
      flyttade.push({ id: r.id || r.kallrad, kund: r.kund, insats: r.insats, datum: r.datum, fran: gammal, till: r.start, minuter: dur });
    }
    lagg(r, bast, +1);
  }
  return { rader: kopior, flyttade };
}

/* ---------- Steg B: jämför schemat mot det omfördelade behovet ---------- */

export type JamforRad = { namn: string; fore: string; efter: string; forandring: string; riktning: "upp" | "ner" | "lika" };

function intervallText(timmar: number[]) {
  const grupper: string[] = [];
  let start: number | null = null;
  for (let t = 0; t <= 24; t++) {
    if (timmar.includes(t)) {
      if (start == null) start = t;
    } else if (start != null) {
      grupper.push(`${String(start).padStart(2, "0")}–${String(t).padStart(2, "0")}`);
      start = null;
    }
  }
  return grupper;
}

export function jamfor(
  fore: Lage,
  efter: Lage,
  flyttade: Flytt[],
  fmt: { h: (x: number) => string; kr: (x: number) => string; pct: (x: number) => string },
  vikarie?: { antalBorttagna: number; antalBehalls: number } | null,
  varningar?: string[],
) {

  const rad = (namn: string, f: number, e: number, form: (x: number) => string, battreNer: boolean, oforandrat = false): JamforRad => {
    const diff = e - f;
    const lika = Math.abs(diff) < 0.05;
    return {
      namn,
      fore: form(f),
      efter: oforandrat ? "oförändrat" : form(e),
      forandring: oforandrat ? "–" : lika ? "–" : `${diff > 0 ? "+" : "−"}${form(Math.abs(diff))}`,
      riktning: lika || oforandrat ? "lika" : (battreNer ? diff < 0 : diff > 0) ? "upp" : "ner",
    };
  };

  const tabell: JamforRad[] = [
    rad("Planerade personaltimmar", fore.schematidH, efter.schematidH, fmt.h, true),
    rad("Kundernas behov", fore.personalbehovH, efter.personalbehovH, fmt.h, false, true),
    rad("Obemannat kundbehov", fore.obemannatKundbehovH, efter.obemannatKundbehovH, fmt.h, true),
    rad("Otäckt dimensionerande resursbehov", fore.otacktDimensionerandeResursH, efter.otacktDimensionerandeResursH, fmt.h, true),
    rad("Överbemanning", fore.overkapacitetH, efter.overkapacitetH, fmt.h, true),
    rad("Matchning mot behov", fore.matchningPct, efter.matchningPct, fmt.pct, false),
    rad("Kundnära tid", fore.kundnaraPct, efter.kundnaraPct, fmt.pct, false),
    rad("Täckt behov", fore.tackningPct, efter.tackningPct, fmt.pct, false),
    rad("Personalkostnad", fore.kostnad, efter.kostnad, fmt.kr, true),
    rad("Beräknad intäkt", fore.intakt, efter.intakt, fmt.kr, false),
    rad("Ekonomiskt resultat", fore.resultat, efter.resultat, fmt.kr, false),
  ];


  // Timmar där bemanningen är för hög respektive för låg mot behovet.
  const minska = efter.perTimme.filter((t) => t.bemanning - t.behov > 0.6).map((t) => t.timme);
  const forstark = efter.perTimme.filter((t) => t.behov - t.bemanning > 0.25).map((t) => t.timme);

  const punkter: string[] = [];
  punkter.push(
    flyttade.length
      ? `${flyttade.length} flyttbara insatser har fått nya tider inom sitt tillåtna fönster.`
      : "Inga flyttbara insatser behövde nya tider – behovet var redan jämnt fördelat.",
  );
  punkter.push("Samtliga fasta insatser ligger kvar på sin ursprungliga tid.");
  if (vikarie) {
    if (vikarie.antalBorttagna) punkter.push(`${vikarie.antalBorttagna} vikariepass kunde tas bort – behovet täcks av ordinarie personal.`);
    if (vikarie.antalBehalls) punkter.push(`${vikarie.antalBehalls} vikariepass behöver tillsättas – de fyller ett verkligt gap i bemanningen.`);
  }
  if (minska.length) punkter.push(`Bemanningen kan minskas kl. ${intervallText(minska).join(", ")} – där finns mer personal än behov.`);
  if (forstark.length) punkter.push(`Bemanningen behöver förstärkas kl. ${intervallText(forstark).join(", ")} – där räcker inte personalen till.`);
  const diffObem = efter.obemannadeIntervall - fore.obemannadeIntervall;
  if (diffObem !== 0) punkter.push(`Antalet intervall med obemannat behov ändras med ${diffObem > 0 ? "+" : "−"}${Math.abs(diffObem)}.`);
  const diffOver = efter.overkapacitetH - fore.overkapacitetH;
  if (Math.abs(diffOver) >= 0.05) punkter.push(`Överkapaciteten ändras med ${diffOver > 0 ? "+" : "−"}${fmt.h(Math.abs(diffOver))}.`);
  if (efter.tackningPct + 0.05 < fore.tackningPct) {
    punkter.push(
      `Täckt behov sjönk från ${fmt.pct(fore.tackningPct)} till ${fmt.pct(efter.tackningPct)}. Lexikografisk optimering maximerar täckning före kostnad, så detta betyder att högre täckning inte gick att nå utan att bryta hårda regler eller utan mer tillgänglig personal – inte att kostnaden har prioriterats.`,
    );
  }
  if (fore.modellFel || efter.modellFel) {
    punkter.push("Modellfel: planerad inom-pass-tid rymdes inte i arbetspassen och har inte räknats som osynlig extra tid.");
  }
  for (const v of varningar || []) punkter.push(v);
  punkter.push("Appen föreslår justeringar och räknar om siffrorna – den lägger inte ett färdigt lagligt schema automatiskt.");

  return { tabell, punkter, minska: intervallText(minska), forstark: intervallText(forstark) };

}

/* ============================================================================
 *  TILLÄGG TILL modell.ts – schemaoptimering (steg B) + styrande villkor
 *  Klistra in HELA detta block i slutet av src/lib/bb/modell.ts.
 *  Det använder era befintliga typer (DatumPass, Slot, Lage) och hjälpare.
 *  Rör inget annat i filen.
 * ========================================================================== */

/* ---------- Medarbetare med villkor (matchar Medarbetare-komponentens fält) ---------- */
export type MedarbetareVillkor = {
  namn: string;
  grad: number;                 // sysselsättningsgrad %
  vikarie?: boolean;
  samordnare?: boolean;
  delegering?: boolean;
  nattbehorig?: boolean;
  jour?: boolean;
  passprofil?: "blandat" | "dag" | "kvall" | "natt";
  helggrad?: "varannan" | "var3" | "alla" | "inga";
  tidigast?: string;            // "06:30"
  senast?: string;              // "23:00"
  maxdag?: number;              // max arbetsdagar i följd
  franvaro?: null | "ledig1v" | "halvtid" | "semester";
  timkostnad?: number;
};

export type SchemaVarning = { namn: string; typ: string; text: string };
export type SchemaForandring = { typ: string; namn: string; datum: string; text: string };

export const REGLER = {
  dygnsvila: 11, maxRad: 5, jourStart: "23:00", jourSlut: "06:30", veckotimmar: 40,
  /** Hela jourarbetspasset: 15:00 → 10:00 dagen efter. Sovande jour ligger 23:00–06:30 inuti passet. */
  jourPassStart: "15:00", jourPassSlut: "10:00",
  /** Arbetstidslagen: högst 48 h jourtid per fyra veckor och 50 h per kalendermånad. */
  jourMax4v: 48, jourMaxManad: 50,
};

const toMinR = (h: string) => { const m = String(h).match(/(\d{1,2}):(\d{2})/); return m ? Number(m[1] ?? 0) * 60 + Number(m[2] ?? 0) : 0; };
const klockaR = (m: number) => { const x = ((Math.round(m) % 1440) + 1440) % 1440; return `${String(Math.floor(x / 60)).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`; };
const veckaNr = (datum: string, fran: string) => Math.floor((+new Date(datum + "T00:00:00Z") - +new Date(fran + "T00:00:00Z")) / 86400000 / 7);
const arHelg = (datum: string) => { const wd = new Date(datum + "T12:00:00Z").getUTCDay(); return wd === 0 || wd === 6; };

/* ---------- Regelkontroll: dygnsvila, max dagar i följd, SSG, helg, frånvaro ---------- */
export function kontrolleraPass(
  pass: DatumPass[], medarbetare: MedarbetareVillkor[], veckor: number, fran?: string
): SchemaVarning[] {
  const varn: SchemaVarning[] = [];
  const per = new Map<string, DatumPass[]>();
  // Vikarie- och vakanspass kontrolleras som ordinarie pass (de flyttas dock aldrig av optimeringen).
  for (const p of pass) if (!p.jour) { (per.get(p.namn) ?? per.set(p.namn, []).get(p.namn)!).push(p); }
  const abs = (p: DatumPass) => { const d = Math.round(+new Date(p.datum + "T00:00:00Z") / 60000); const s = toMinR(p.start); let e = toMinR(p.slut); if (e <= s) e += 1440; return { s: d + s, e: d + e }; };
  for (const [namn, ps] of per) {
    const t = ps.map((p) => ({ p, ...abs(p) })).sort((a, b) => a.s - b.s);
    for (let i = 1; i < t.length; i++) { const a = t[i - 1], b = t[i]; if (!a || !b) continue; const vila = (b.s - a.e) / 60; if (vila >= 0 && b.p.datum !== a.p.datum && vila < REGLER.dygnsvila) varn.push({ namn, typ: "dygnsvila", text: `${namn}: ${vila.toFixed(1)} h vila mellan ${a.p.datum} och ${b.p.datum} (<${REGLER.dygnsvila} h)` }); }
    const m = medarbetare.find((x) => x.namn === namn);
    const dagar = [...new Set(ps.map((p) => p.datum))].sort();
    let rad = 1; const maxd = m?.maxdag ?? REGLER.maxRad;
    for (let i = 1; i < dagar.length; i++) { const nu = dagar[i], fore = dagar[i - 1]; if (!nu || !fore) continue; const diff = Math.round((+new Date(nu) - +new Date(fore)) / 86400000); rad = diff === 1 ? rad + 1 : 1; if (rad > maxd) { varn.push({ namn, typ: "maxRad", text: `${namn}: ${rad} arbetsdagar i följd (max ${maxd})` }); break; } }
    if (m) {
      const tak = (m.grad / 100) * REGLER.veckotimmar * veckor; const tim = ps.reduce((s, p) => s + p.timmar, 0);
      if (tim > tak * 1.05) varn.push({ namn, typ: "ssg", text: `${namn}: ${tim.toFixed(1)} h överstiger SSG-tak ${tak.toFixed(1)} h` });
      if (fran) {
        const hset = new Set<number>(); if (m.helggrad === "alla") { for (let v = 0; v < veckor; v++) hset.add(v); } else if (m.helggrad === "var3") { for (let v = 0; v < veckor; v += 3) hset.add(v); } else if (m.helggrad !== "inga") { for (let v = 0; v < veckor; v += 2) hset.add(v); }
        let helgFel = 0, franFel = 0;
        for (const p of ps) { const v = veckaNr(p.datum, fran); if (arHelg(p.datum) && m.helggrad && !hset.has(v)) helgFel++; if (m.franvaro === "ledig1v" && v % 4 === 3) franFel++; else if (m.franvaro === "halvtid" && v % 2 === 1) franFel++; else if (m.franvaro === "semester" && v >= veckor - 2) franFel++; }
        if (helgFel) varn.push({ namn, typ: "helg", text: `${namn}: ${helgFel} helgpass utanför sin helgtjänstgöring (${m.helggrad})` });
        if (franFel) varn.push({ namn, typ: "franvaro", text: `${namn}: ${franFel} pass under planerad frånvaro/ledighet` });
      }
    }
  }
  /* Sovande jour har egna regler: jourtiden räknas separat från arbetstiden och
   * får enligt arbetstidslagen vara högst 48 h per fyra veckor och 50 h per
   * kalendermånad. Jourpassen ingår därför inte i kontrollerna ovan. */
  const jourPer = new Map<string, DatumPass[]>();
  for (const p of pass) if (p.jour) { const l = jourPer.get(p.namn); if (l) l.push(p); else jourPer.set(p.namn, [p]); }
  for (const [namn, ps] of jourPer) {
    const sorterade = ps.slice().sort((a, b) => a.datum.localeCompare(b.datum));
    // Rullande fyraveckorsfönster (28 dagar).
    for (let i = 0; i < sorterade.length; i++) {
      const start = sorterade[i]; if (!start) continue;
      const gransen = +new Date(start.datum + "T00:00:00Z") + 27 * 86400000;
      let sum = 0;
      for (let j = i; j < sorterade.length; j++) { const q = sorterade[j]; if (!q) continue; if (+new Date(q.datum + "T00:00:00Z") > gransen) break; sum += q.timmar; }
      if (sum > REGLER.jourMax4v) {
        varn.push({ namn, typ: "jour4v", text: `${namn}: ${sum.toFixed(1)} h jourtid under fyra veckor från ${start.datum} (max ${REGLER.jourMax4v} h)` });
        break;
      }
    }
    // Kalendermånad.
    const perManad = new Map<string, number>();
    for (const p of sorterade) { const k = p.datum.slice(0, 7); perManad.set(k, (perManad.get(k) || 0) + p.timmar); }
    for (const [manad, sum] of perManad) {
      if (sum > REGLER.jourMaxManad) varn.push({ namn, typ: "jourManad", text: `${namn}: ${sum.toFixed(1)} h jourtid i ${manad} (max ${REGLER.jourMaxManad} h per kalendermånad)` });
    }
  }
  return varn;
}

/* ---------- STEG B: schemaoptimering (regelbaserad lokal sökning) ----------
 * Kostnad per slot: brist (behov > bemanning) väger 3, överkapacitet väger 1,5.
 * Drag per pass: flytta i tid, korta, förlänga (inom SSG). Accepteras bara om
 * total kostnad sjunker OCH regelläget inte blir sämre. Jour rörs aldrig.
 * Respekterar passprofil, individuella arbetstider, helggrad och frånvaro. */
export function optimeraSchema(opts: {
  pass: DatumPass[]; rader: any[]; fran: string; till: string;
  medarbetare: MedarbetareVillkor[]; timkostnad: number;
}): { pass: DatumPass[]; forandringar: SchemaForandring[]; varningar: SchemaVarning[] } {
  const { pass, rader, fran, till, medarbetare } = opts;
  const lista = dagar(fran, till); const nD = lista.length; const veckor = Math.max(1, Math.round(nD / 7));
  const idx = new Map(lista.map((d, i) => [d, i]));
  const kurva = analysera({ rader, pass, fran, till, timkostnad: opts.timkostnad } as any);
  const dim = kurva.slots.map((s) => s.dimensionerat), ra = kurva.slots.map((s) => s.behov);
  const N = nD * 48; const jS = toMinR(REGLER.jourStart), jE = toMinR(REGLER.jourSlut);
  const P: DatumPass[] = pass.map((p) => ({ ...p }));
  const medMap = new Map(medarbetare.map((m) => [m.namn, m]));
  const tak = new Map(medarbetare.map((m) => [m.namn, (m.grad / 100) * REGLER.veckotimmar * veckor]));
  const bem = new Int16Array(N);
  const slots = (p: DatumPass): number[] => { const di = idx.get(p.datum); if (di == null) return []; const s = toMinR(p.start); let e = toMinR(p.slut); if (e <= s) e += 1440; const out: number[] = []; for (let sl = Math.floor(s / 30); sl < Math.ceil(e / 30); sl++) { const d2 = di + (sl >= 48 ? 1 : 0); if (d2 >= nD) break; out.push(d2 * 48 + (sl % 48)); } return out; };
  const app = (p: DatumPass, t: number) => { for (const c of slots(p)) bem[c] = (bem[c] ?? 0) + t; };
  for (const p of P) if (!p.jour) app(p, +1);
  const kundBrist = () => {
    let s = 0;
    for (let c = 0; c < N; c++) s += Math.max(0, (ra[c] ?? 0) - (bem[c] ?? 0));
    return s;
  };
  const dimBrist = () => {
    let s = 0;
    for (let c = 0; c < N; c++) s += Math.max(0, (dim[c] ?? 0) - (bem[c] ?? 0));
    return s;
  };
  const kostSlot = (c: number) => { const b = bem[c] ?? 0; return Math.max(0, (dim[c] ?? 0) - b) * 3 + Math.max(0, b - (ra[c] ?? 0)) * 1.5; };
  const kostFor = (cells: number[]) => cells.reduce((k, c) => k + kostSlot(c), 0);
  const timPer = () => { const m = new Map<string, number>(); for (const p of P) if (!p.jour) m.set(p.namn, (m.get(p.namn) || 0) + p.timmar); return m; };
  const bas = new Map(medarbetare.map((m) => [m.namn, kontrolleraPass(pass.filter((p) => p.namn === m.namn), medarbetare, veckor, fran).length]));
  const regelOK = (namn: string) => kontrolleraPass(P.filter((p) => p.namn === namn), medarbetare, veckor, fran).length <= (bas.get(namn) || 0);
  const farJobba = (namn: string, datum: string) => { const m = medMap.get(namn); if (!m) return true; const v = veckaNr(datum, fran); if (m.franvaro === "ledig1v" && v % 4 === 3) return false; if (m.franvaro === "halvtid" && v % 2 === 1) return false; if (m.franvaro === "semester" && v >= veckor - 2) return false; if (arHelg(datum) && m.helggrad && !(new Set(m.helggrad === "alla" ? Array.from({ length: veckor }, (_, i) => i) : m.helggrad === "var3" ? Array.from({ length: veckor }, (_, i) => i).filter((i) => i % 3 === 0) : m.helggrad === "inga" ? [] : Array.from({ length: veckor }, (_, i) => i).filter((i) => i % 2 === 0))).has(v)) return false; return true; };
  const inomTid = (namn: string, s: number, e: number) => { const m = medMap.get(namn); let lo = jE, hi = jS; if (m) { if (m.tidigast) lo = Math.max(lo, toMinR(m.tidigast)); if (m.senast) hi = Math.min(hi, toMinR(m.senast)); if (m.passprofil === "dag") hi = Math.min(hi, 17 * 60); else if (m.passprofil === "kvall") lo = Math.max(lo, 14 * 60); else if (m.passprofil === "natt") return false; } return s >= lo && e <= hi && e - s >= 120 && e - s <= 600; };
  const forandringar: SchemaForandring[] = [];
  const testa = (p: DatumPass, q: DatumPass) => {
    const brist0 = kundBrist();
    const dim0 = dimBrist();
    const beror = [...new Set([...slots(p), ...slots(q)])];
    const k0 = kostFor(beror);
    app(p, -1); app(q, +1);
    const brist1 = kundBrist();
    const dim1 = dimBrist();
    const k1 = kostFor(beror);
    app(q, -1); app(p, +1);
    return { dBrist: brist1 - brist0, dDim: dim1 - dim0, dTim: q.timmar - p.timmar, dKost: k1 - k0 };
  };
  const battre = (t: { dBrist: number; dTim: number; dKost: number }) =>
    t.dBrist < -1e-9 || (Math.abs(t.dBrist) < 1e-9 && t.dTim < -1e-9) || (Math.abs(t.dBrist) < 1e-9 && Math.abs(t.dTim) < 1e-9 && t.dKost < -0.51);
  const gor = (i: number, q: Partial<DatumPass>, typ: string, text: string) => { const p = P[i]; if (!p) return false; app(p, -1); const g = { ...p }; Object.assign(p, q); if (!regelOK(p.namn)) { Object.assign(p, g); app(p, +1); return false; } app(p, +1); forandringar.push({ typ, namn: p.namn, datum: p.datum, text }); return true; };

  let forbattrat = true, varv = 0;
  while (forbattrat && varv < 20) { forbattrat = false; varv++; let tim = timPer();
    for (let i = 0; i < P.length; i++) { const p = P[i]; if (!p || p.jour || p.vakant || p.vikarie) continue; if (!farJobba(p.namn, p.datum)) continue;
      const s = toMinR(p.start); let e = toMinR(p.slut); if (e <= s) e += 1440; const dur = e - s;
      let bast: { q: DatumPass; typ: string; text: string } | null = null, bd: ReturnType<typeof testa> | null = null;
      for (const d of [-300, -240, -180, -120, -90, -60, -45, -30, -15, 15, 30, 45, 60, 90, 120, 180, 240, 300]) { const ns = s + d, ne = e + d; if (ns < 0 || !inomTid(p.namn, ns, ne)) continue; const q = { ...p, start: klockaR(ns), slut: klockaR(ne) }; const t = testa(p, q); if (battre(t) && (!bd || t.dBrist < bd.dBrist - 1e-9 || (Math.abs(t.dBrist - bd.dBrist) < 1e-9 && (t.dTim < bd.dTim - 1e-9 || (Math.abs(t.dTim - bd.dTim) < 1e-9 && t.dKost < bd.dKost))))) { bd = t; bast = { q, typ: "flyttat", text: `${p.namn} ${p.datum}: pass flyttat ${p.start}–${p.slut} → ${q.start}–${q.slut}` }; } }
      for (const d of [30, 60]) { if (dur - d < 180) break; for (const sida of ["slut", "start"]) { const ns = sida === "start" ? s + d : s, ne = sida === "slut" ? e - d : e; if (!inomTid(p.namn, ns, ne)) continue; const q = { ...p, start: klockaR(ns), slut: klockaR(ne), timmar: (ne - ns) / 60 }; const t = testa(p, q); if (battre(t) && (!bd || t.dBrist < bd.dBrist - 1e-9 || (Math.abs(t.dBrist - bd.dBrist) < 1e-9 && (t.dTim < bd.dTim - 1e-9 || (Math.abs(t.dTim - bd.dTim) < 1e-9 && t.dKost < bd.dKost))))) { bd = t; bast = { q, typ: "kortat", text: `${p.namn} ${p.datum}: pass kortat ${p.start}–${p.slut} → ${q.start}–${q.slut}` }; } } }
      const utr = (tak.get(p.namn) || 0) - (tim.get(p.namn) || 0);
      if (utr >= 0.5) for (const d of [30, 60]) { if (d / 60 > utr + 0.01) break; for (const sida of ["slut", "start"]) { const ns = sida === "start" ? s - d : s, ne = sida === "slut" ? e + d : e; if (ns < 0 || !inomTid(p.namn, ns, ne)) continue; const q = { ...p, start: klockaR(ns), slut: klockaR(ne), timmar: (ne - ns) / 60 }; const t = testa(p, q); if (battre(t) && (!bd || t.dBrist < bd.dBrist - 1e-9 || (Math.abs(t.dBrist - bd.dBrist) < 1e-9 && (t.dTim < bd.dTim - 1e-9 || (Math.abs(t.dTim - bd.dTim) < 1e-9 && t.dKost < bd.dKost))))) { bd = t; bast = { q, typ: "forlangt", text: `${p.namn} ${p.datum}: pass förlängt ${p.start}–${p.slut} → ${q.start}–${q.slut}` }; } } }
      if (bast && gor(i, bast.q, bast.typ, bast.text)) { forbattrat = true; tim = timPer(); }
    }
  }
  return { pass: P, forandringar, varningar: kontrolleraPass(P, medarbetare, veckor, fran) };
}

/* ---------- Styrande villkor (ersätter FORINSTALLDA_VILLKOR) ---------- */
export const STYRANDE_VILLKOR: { grupp: string; villkor: [string, string, string, string, string][] }[] = [
  { grupp: "Arbetstidsregler", villkor: [
    ["Minsta dygnsvila", "11", "h", "Röd kontroll vid kortare vila", "krav"],
    ["Veckovila", "36", "h/vecka", "Röd kontroll vid kortare vila", "krav"],
    ["Max sammanhängande arbete", "4", "h", "Verksamhetsregel", "krav"],
    ["Långpass – gul varning", "10", "h", "Optimeringsgräns", "gul"],
    ["Långpass – röd varning", "12", "h", "Kräver särskild bedömning", "krav"],
    ["Max arbetsdagar i följd", "5", "dagar", "Normalläge", "krav"],
    ["Minsta fridagar", "9", "dagar/4 v", "Fast lokal regel", "krav"],
    ["Schema i förväg", "14", "dagar", "Två veckor enligt avtal", "krav"],
    ["Längsta schemaperiod", "16", "veckor", "Avtalets huvudregel", "krav"],
    ["Individuell kontrollperiod", "28", "dagar", "Fyra veckor", "info"],
  ] },
  { grupp: "Natt och jour", villkor: [
    ["Jourarbetspass", "15:00–10:00", "tid", "Hela passet, slutar dagen efter", "ram"],
    ["Sovande jour", "23:00–06:30", "tid", "Alla dagar, även helg", "krav"],
    ["Max jourtid per fyra veckor", "48", "h", "Arbetstidslagen – egen regel för sovande jour", "krav"],
    ["Max jourtid per kalendermånad", "50", "h", "Arbetstidslagen – alternativ gräns", "krav"],
    ["Jourtid räknas separat", "Ja", "regel", "Ingår inte i arbetstid, dygnsvila eller SSG-tak", "info"],
    ["Vaken natt – grundbemanning", "1", "medarbetare", "Nattgolv", "krav"],
    ["Önskat max nattpass i följd", "2", "nätter", "Planeringsmål", "mål"],
    ["Nattserie – gul varning", "3", "nätter", "Kräver bedömning", "gul"],
    ["Nattserie – röd varning", "4", "nätter", "Undviks", "krav"],
    ["Nattbehörighet", "Krävs", "behörighet", "För jour och nattpass", "krav"],
  ] },
  { grupp: "Raster", villkor: [
    ["Standardrast", "30", "minuter", "Antagen obetald", "info"],
    ["Standard rasttyp", "Rast", "val", "Dras från operativ tid", "info"],
    ["Scenario", "Förslag med rast", "val", "Styr etiketter", "info"],
  ] },
  { grupp: "Kompetens och kontinuitet", villkor: [
    ["Delegering", "Alla", "behörighet", "Samtlig personal", "uppfyllt"],
    ["Samordnare", "Utses", "individ", "Dagtid", "individ"],
    ["Kontinuitet max personer", "5", "personer/kund", "Färre är bättre", "mål"],
    ["Andel kundnära tid – mål", "75", "%", "Pilotmål", "mål"],
    ["Effektivitetsmål", "75", "%", "Andel kundnära tid", "mål"],
    ["Fasta insatser", "Oförändrade", "regel", "Ligger kvar på tid", "krav"],
  ] },
  { grupp: "Sysselsättningsgrad", villkor: [
    ["Veckoarbetstid dag/kväll", "37", "h/vecka", "Blandad vardag/helg", "krav"],
    ["Veckoarbetstid ständig natt", "36 h 20 min", "h/vecka", "Kollektivavtal", "krav"],
    ["Helgprincip", "Varannan helg – heltid", "val", "Deltid utifrån SSG", "info"],
    ["SSG-tolerans", "0,01", "timmar", "Avvikelse under = 0", "info"],
  ] },
  { grupp: "Ekonomiska ramar", villkor: [
    ["Intäkt per kund och dygn", "2500", "kr", "Lämnad uppgift", "ram"],
    ["Timkostnad", "270", "kr/h", "Inkl. sociala avgifter", "ram"],
    ["Personalbudget", "Per verksamhet", "kr/månad", "Sätts i Ekonomi", "ram"],
    ["Bemanningsbuffert", "4", "% av timmar", "Korttidsfrånvaro/VAB", "ram"],
    ["Ekonomisk reserv", "6", "% av budget", "Övertid/akut", "ram"],
    ["Korttidsfrånvaro", "4", "%", "Antagande", "info"],
  ] },
  { grupp: "Individuella villkor", villkor: [
    ["Passprofil", "Per individ", "val", "Dag/kväll/natt styr optimeringen", "individ"],
    ["Helgtjänstgöring", "Per individ", "val", "Varannan/var tredje/alla/inga", "individ"],
    ["Tidigaste start / senaste slut", "Per individ", "tid", "Egna arbetstidsfönster", "individ"],
    ["Frånvaro/ledighet", "Per individ", "val", "Ledig vecka, halvtid, semester", "individ"],
    ["Max dagar i följd (individ)", "Per individ", "dagar", "Kan avvika från 5", "individ"],
    ["Anställningsform", "Månadsanställd", "info", "Standard", "info"],
  ] },
  { grupp: "Rörliga villkor – Kund (datumstyrda)", villkor: [
    ["Sjukhus/frånvaro", "Mall", "typ", "Kund tillfälligt borta", "gul"],
    ["Planerad hemresa/semester", "Mall", "typ", "Behov pausas", "gul"],
    ["Ny kund", "Mall", "typ", "Kund tillkommer", "gul"],
    ["Kund avslutas", "Mall", "typ", "Behov upphör", "gul"],
    ["Förändrat behov/beslut", "Mall", "typ", "Ändrad nivå", "gul"],
    ["Ändrade insatstider", "Mall", "typ", "Nya tider", "gul"],
    ["Extra/inställd aktivitet", "Mall", "typ", "Tillfällig ändring i aktivitet", "gul"],
    ["Insats får flyttas", "Mall", "typ", "Görs flyttbar", "gul"],
    ["Insats låses", "Mall", "typ", "Fast tid", "gul"],
    ["Dubbelbemanning", "Mall", "typ", "Två medarbetare", "gul"],
    ["Vakennatt", "Mall", "typ", "Aktiv natt", "gul"],
    ["Kompetens/delegering", "Mall", "typ", "Särskilt krav", "gul"],
    ["Kontinuitetskrav", "Mall", "typ", "Begränsat antal", "gul"],
    ["Samplanering", "Mall", "typ", "Insatser samordnas", "gul"],
    ["Restid/ledsagning", "Mall", "typ", "Tid utanför hemmet", "gul"],
  ] },
  { grupp: "Rörliga villkor – Intäkt & personal", villkor: [
    ["Ändrad ersättning", "Mall", "typ", "Ny nivå", "gul"],
    ["Tillägg dubbelbemanning", "Mall", "typ", "Extra ersättning", "gul"],
    ["Tillägg vakennatt", "Mall", "typ", "Aktiv natt", "gul"],
    ["Retroaktiv ersättning", "Mall", "typ", "Justering bakåt", "gul"],
    ["Fast ledig dag", "Mall", "typ", "Visst datum", "individ"],
    ["Administrativ tid", "Mall", "typ", "Möte/utbildning", "individ"],
    ["Utbildning/möte", "Mall", "typ", "Ur produktion", "individ"],
    ["Ej tillgänglig", "Mall", "typ", "Frånvaro", "individ"],
    ["Ändrad nattbehörighet", "Mall", "typ", "Behörighet ändras", "individ"],
    ["Ändrad delegering", "Mall", "typ", "Ges/dras", "individ"],
    ["Tillägg omfattande behov", "Mall", "typ", "Högre ersättningsnivå", "gul"],
    ["Reducerad ersättning vid frånvaro", "Mall", "typ", "Avdrag vid kundfrånvaro", "gul"],
    ["Semester/ledighet", "Mall", "typ", "Planerad ledighet", "individ"],
    ["Tillfällig vikarie", "Mall", "typ", "Vikarie tillsätts", "individ"],
  ] },
  { grupp: "Beräkning och kontroll", villkor: [
    ["Tidsintervall", "15", "minuter", "Samtidigt resursbehov", "info"],
    ["Tröskel nytt schemaförslag", "2", "dagar", "Kräver ny optimering", "info"],
    ["Max kunder i register", "20", "kunder", "Reserverade rader", "info"],
    ["Max periodlängd", "31", "dagar", "Pilotmodellen", "info"],
  ] },
];

