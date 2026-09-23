import {
  DEFAULT_WORK_TIME_MODEL_ID,
  STANDARD_WORK_TIME_MODELS,
  harTillrackligArbetstidsmodell,
  type WorkTimeModel,
  type WorkTimeWindow,
} from "./arbetstid";

/** Presentationsadapter för VC-flödet. Ingen ny beräkning av täckning, kostnad eller regler. */

export type ProcessStegLage = "ej" | "pa" | "klar" | "varning" | "blockerad";

/** Tidslägen är Före → Balans → Utfall. Övriga poster är handlingar inom läget. */
export const PROCESS_STEG = [
  { id: "fore", label: "Före", typ: "lage" as const },
  { id: "skapa", label: "Skapa balans", typ: "handling" as const },
  { id: "balans", label: "Balans", typ: "lage" as const },
  { id: "resultat", label: "Granska balans", typ: "handling" as const },
  { id: "schemaforslag", label: "Godkänn balans", typ: "handling" as const },
  { id: "nyckeltal", label: "Utfall", typ: "lage" as const },
] as const;

export const TIDSLINJE_ORDNING = ["Före", "Balans", "Utfall"] as const;
export const PROCESS_HANDLINGAR = ["Skapa balans", "Granska balans", "Godkänn balans"] as const;

export const TIDSLAGEN = [
  { id: "fore", label: "Före", text: "Så ser bemanningen ut i det underlag som lästs in." },
  { id: "balans", label: "Balans", text: "Så planerar vi schemaperioden." },
  { id: "utfall", label: "Utfall", text: "Så blev schemaperioden." },
] as const;

export type TidslageId = (typeof TIDSLAGEN)[number]["id"];

export function getTidslage(d: { harUnderlag?: boolean; harBalans: boolean; harUtfall?: boolean }): TidslageId {
  if (d.harUtfall) return "utfall";
  if (d.harBalans) return "balans";
  return "fore";
}

export function tidslageText(id: TidslageId) {
  return TIDSLAGEN.find((t) => t.id === id)!;
}

export const TACKT_BEHOV_FORKLARING =
  "Täckt behov = bemannat kundbehov / totalt kundbehov. Svarar på om det dimensionerande kund- och verksamhetsbehovet är bemannat (inkl. dubbelbemanning och närvarokrav när de ingår i behovet).";
export const KUNDNARA_FORKLARING =
  "Kundnära tid = schemalagd kundnära arbetstid / total schemalagd arbetstid. Effektivitetsmått; behöver inte vara 100 %. Sovande jour räknas inte som kundnära om ingen kundnära aktivitet utförs.";
export const MATCHNING_FORKLARING =
  "Matchning mot behov = 1 − (otäckt dimensionerande resurstid / totalt dimensionerande resursbehov). Mäter hur bemanningen träffar behovskurvan i tiden, inte samma sak som täckt behov eller kundnära tid.";
export const UNDERKAPACITET_FORKLARING =
  "Underkapacitet = summa (dimensionerande behov − schemalagd bemanning) × 0,5 h i 30-minutersintervall där bemanningen understiger det dimensionerande behovet.";
export const OVERKAPACITET_FORKLARING =
  "Överkapacitet = summa (schemalagd bemanning − rått kundbehov) × 0,5 h i intervall där bemanningen överstiger rått kundbehov. Formeln är oförändrad; den använder rått kundbehov, inte samma dimensionerande kurva som underkapacitet.";
export const KAPACITET_FORKLARING =
  "Överkapacitet betyder att bemanning finns när behovet är lägre. Underkapacitet betyder att bemanningsbehov saknar motsvarande bemanning vid andra tider. De är inte samma sak som täckt behov.";
export const MEDARBETARE_ANDRAD_TEXT =
  "Medarbetarvillkoren har ändrats. Granska förändringen innan du skapar bemanningsbalans.";

export const VC_FORBJUDNA_ORD = [
  "Optimeringsmotorn",
  "optimizer",
  "OPTIMIZER_URL",
  "reservläge",
  "Adress saknas",
  "INFEASIBLE",
  "CP-SAT",
  "regelbibliotek",
] as const;

export function vcTextArRen(text: string) {
  const t = text.toLowerCase();
  return !VC_FORBJUDNA_ORD.some((ord) => t.includes(ord.toLowerCase()));
}

export const TRE_OMRADEN_RUBRIKER = ["Kundnära tid", "Hållbara scheman", "Rätt resurs i rätt tid"] as const;

export type MotorUiSummary = {
  status: string;
  coveragePercent: number | null;
  customerNearPercent: number | null;
  cost: number;
  hardViolations: { rule?: string; message?: string }[];
  warnings: { rule?: string; message?: string }[];
  changedShiftCount: number;
  lockedShiftCount: number;
  explanationSummary: string;
  performanceSummary: string;
};

const TOM_SUMMARY: MotorUiSummary = {
  status: "NOT_RUN",
  coveragePercent: null,
  customerNearPercent: null,
  cost: 0,
  hardViolations: [],
  warnings: [],
  changedShiftCount: 0,
  lockedShiftCount: 0,
  explanationSummary: "",
  performanceSummary: "",
};

/** VC-svenska för motorstatus. Tekniska koder visas inte som rubrik. */
export function vcStatusText(status: string | null | undefined, opts?: { jourResursbrist?: boolean }) {
  const s = String(status || "").toUpperCase();
  if (opts?.jourResursbrist || s === "JOUR_CAPACITY_SHORTFALL") {
    return "Bemanningsbalans kan inte skapas fullt ut med registrerade resurser";
  }
  if (s === "OPTIMAL") return "Förslaget är beräknat och bevisat så långt tidsgränsen räckte";
  if (s === "FEASIBLE") return "Ett giltigt förslag finns";
  if (s === "INFEASIBLE") return "Ingen giltig bemanning kunde skapas med nuvarande underlag";
  if (s === "UNKNOWN") return "Beräkningen avbröts innan ett förslag fanns";
  if (s === "MODEL_INVALID") return "Förslaget stoppades av kontrollen";
  if (s === "422") return "Underlaget avvisades";
  if (s === "503") return "Beräkningen är inte tillgänglig just nu";
  if (s === "NOT_RUN") return "Ingen beräkning är gjord ännu";
  return "Beräkning saknas";
}

export function lasMotorSummary(raw: unknown): MotorUiSummary | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const s = o["summary"];
  if (s && typeof s === "object") {
    const x = s as Record<string, unknown>;
    return {
      status: String(x["status"] || o["solverStatus"] || "NOT_RUN"),
      coveragePercent: typeof x["coveragePercent"] === "number" ? x["coveragePercent"] : null,
      customerNearPercent: typeof x["customerNearPercent"] === "number" ? x["customerNearPercent"] : null,
      cost: Number(x["cost"] || 0),
      hardViolations: Array.isArray(x["hardViolations"]) ? (x["hardViolations"] as MotorUiSummary["hardViolations"]) : [],
      warnings: Array.isArray(x["warnings"]) ? (x["warnings"] as MotorUiSummary["warnings"]) : [],
      changedShiftCount: Number(x["changedShiftCount"] || 0),
      lockedShiftCount: Number(x["lockedShiftCount"] || 0),
      explanationSummary: String(x["explanationSummary"] || ""),
      performanceSummary: String(x["performanceSummary"] || ""),
    };
  }
  if (typeof o["solverStatus"] === "string" || typeof o["explanation"] === "string") {
    return {
      ...TOM_SUMMARY,
      status: String(o["solverStatus"] || "NOT_RUN"),
      explanationSummary: String(o["explanation"] || "").split(".")[0] ?? "",
      changedShiftCount: Array.isArray(o["forandringar"]) ? o["forandringar"].length : 0,
    };
  }
  return null;
}

export type DelStatus = "ej" | "kompletteras" | "klar" | "forandrad";

export type ReadinessMedarbetare = {
  namn: string;
  vakant?: boolean;
  workTimeModelId?: string;
  workTimeWindows?: WorkTimeWindow[];
  nattbehorig?: boolean | null;
  jour?: boolean | null;
};

/** Indata för att *skapa* balans. KPI och regelbrott i Före-läget ingår inte. */
export type BemanningsbalansReadinessIndata = {
  harKundrader: boolean;
  harSchema: boolean;
  kundGodkand: boolean;
  kundAndradSedanGodkannande?: boolean;
  schemaGodkand: boolean;
  medarbetareAndradSedanGodkannande?: boolean;
  medarbetare: ReadinessMedarbetare[];
  /** Verksamhetens standardmodell. Tom sträng = ingen default. */
  defaultWorkTimeModelId?: string;
  workTimeModels?: WorkTimeModel[];
};

export type BemanningsbalansReadiness = {
  ready: boolean;
  blockingReasons: string[];
  warnings: string[];
  delar: { kund: DelStatus; medarbetare: DelStatus; schema: DelStatus };
  harKunddata: boolean;
  harMedarbetare: boolean;
};

function treVarde(v: boolean | null | undefined): "ja" | "nej" | "okand" {
  if (v === true) return "ja";
  if (v === false) return "nej";
  return "okand";
}

/**
 * Readiness för Före → Skapa balans.
 * Blockerar bara saknad/ogodkänd grunddata. Täckt behov, hårda regelbrott,
 * underkapacitet och överkapacitet i det inlästa nuläget blockerar inte.
 */
export function getBemanningsbalansReadiness(d: BemanningsbalansReadinessIndata): BemanningsbalansReadiness {
  const blockingReasons: string[] = [];
  const warnings: string[] = [];
  const aktiva = (d.medarbetare || []).filter((m) => !m.vakant);
  const harMedarbetare = aktiva.length > 0;
  const harKunddata = !!d.harKundrader;
  const workplace: { workTimeModels: WorkTimeModel[]; defaultWorkTimeModelId?: string } = {
    workTimeModels: d.workTimeModels || [],
  };
  if (d.defaultWorkTimeModelId !== undefined) workplace.defaultWorkTimeModelId = d.defaultWorkTimeModelId;
  const saknarModell = aktiva.filter((m) => (m as { resourceType?: string }).resourceType !== "temporary" && !harTillrackligArbetstidsmodell(m, workplace));

  let kund: DelStatus = "ej";
  if (!harKunddata) kund = "ej";
  else if (!d.kundGodkand) kund = "kompletteras";
  else if (d.kundAndradSedanGodkannande) kund = "forandrad";
  else kund = "klar";

  let schema: DelStatus = "ej";
  if (!d.harSchema) schema = "ej";
  else if (!d.schemaGodkand) schema = "kompletteras";
  else if (d.medarbetareAndradSedanGodkannande) schema = "forandrad";
  else schema = "klar";

  let medarbetare: DelStatus = "ej";
  if (!harMedarbetare) medarbetare = "ej";
  else if (saknarModell.length || !d.schemaGodkand) medarbetare = "kompletteras";
  else if (d.medarbetareAndradSedanGodkannande) medarbetare = "forandrad";
  else medarbetare = "klar";

  if (!harKunddata) blockingReasons.push("Kundbehovet är inte inläst");
  else if (!d.kundGodkand) blockingReasons.push("Kundbehovet är inte godkänt");
  else if (d.kundAndradSedanGodkannande) blockingReasons.push("Kundbehovet är förändrat sedan senaste godkännande");

  if (!d.harSchema) blockingReasons.push("Personalschemat är inte inläst");
  else if (!d.schemaGodkand) blockingReasons.push("Personalschemat är inte godkänt");
  else if (d.medarbetareAndradSedanGodkannande) blockingReasons.push(MEDARBETARE_ANDRAD_TEXT);

  if (!harMedarbetare) blockingReasons.push("Medarbetare är inte inlästa");
  if (harMedarbetare && saknarModell.length) {
    blockingReasons.push(`${saknarModell.length} medarbetare saknar arbetstidsmodell`);
  }

  const natt = aktiva.map((m) => treVarde(m.nattbehorig));
  if (aktiva.length && natt.every((x) => x === "nej")) warnings.push("Ingen medarbetare är angiven som nattbehörig");
  if (aktiva.length && natt.some((x) => x === "okand")) warnings.push("Nattbehörighet är inte angiven för alla medarbetare");

  const unique = [...new Set(blockingReasons)];
  return {
    ready: unique.length === 0,
    blockingReasons: unique,
    warnings,
    delar: { kund, medarbetare, schema },
    harKunddata,
    harMedarbetare,
  };
}

export function skapaBalansHinder(d: {
  kundGodkand: boolean;
  schemaGodkand?: boolean;
  medarbetare: ReadinessMedarbetare[];
  harUnderlag: boolean;
  blockerande?: string[];
  kundAndradSedanGodkannande?: boolean;
  medarbetareAndradSedanGodkannande?: boolean;
  harKundrader?: boolean;
  harSchema?: boolean;
  defaultWorkTimeModelId?: string;
  workTimeModels?: WorkTimeModel[];
}) {
  const indata: BemanningsbalansReadinessIndata = {
    harKundrader: d.harKundrader ?? d.harUnderlag,
    harSchema: d.harSchema ?? d.harUnderlag,
    kundGodkand: d.kundGodkand,
    schemaGodkand: !!d.schemaGodkand,
    medarbetare: d.medarbetare,
  };
  if (d.kundAndradSedanGodkannande !== undefined) indata.kundAndradSedanGodkannande = d.kundAndradSedanGodkannande;
  if (d.medarbetareAndradSedanGodkannande !== undefined) indata.medarbetareAndradSedanGodkannande = d.medarbetareAndradSedanGodkannande;
  if (d.defaultWorkTimeModelId !== undefined) indata.defaultWorkTimeModelId = d.defaultWorkTimeModelId;
  if (d.workTimeModels !== undefined) indata.workTimeModels = d.workTimeModels;
  const r = getBemanningsbalansReadiness(indata);
  const skal = [...r.blockingReasons, ...(d.blockerande || []).filter(Boolean)];
  return { aktiv: skal.length === 0, skal, warnings: r.warnings, delar: r.delar };
}

export function aktivProcessId(tab: string): string {
  if (tab === "motor") return "skapa";
  if (tab === "foreefter") return "balans";
  if (["hem", "kundbehov", "medarbetare", "uppladdning", "underlag"].includes(tab)) return "fore";
  if (PROCESS_STEG.some((s) => s.id === tab)) return tab;
  return tab;
}

export function processStegTab(id: string): string {
  if (id === "fore") return "hem";
  if (id === "balans") return "resultat";
  if (id === "skapa") return "skapa";
  return id;
}

export function processStegLagen(d: {
  aktivTab: string;
  readiness: BemanningsbalansReadiness;
  harResultat: boolean;
  harVarning: boolean;
  schemaForslagGodkant?: boolean;
}): { id: string; label: string; lage: ProcessStegLage; typ: "lage" | "handling" }[] {
  const aktiv = aktivProcessId(d.aktivTab);
  const iBalansFlik = ["balans", "resultat", "schemaforslag"].includes(aktiv);
  return PROCESS_STEG.map((steg) => {
    let lage: ProcessStegLage = "ej";
    if (steg.id === "fore") {
      if (!d.readiness.harKunddata && !d.readiness.harMedarbetare) lage = "ej";
      else if (aktiv === "fore") lage = "pa";
      else lage = "klar";
    } else if (steg.id === "skapa") {
      if (!d.readiness.ready && !d.harResultat) lage = "blockerad";
      else if (d.harResultat) lage = "klar";
      else if (aktiv === "skapa") lage = "pa";
      else lage = "ej";
    } else if (steg.id === "balans") {
      if (!d.harResultat) lage = "ej";
      else if (iBalansFlik) lage = "pa";
      else lage = "klar";
    } else if (steg.id === "resultat") {
      if (!d.harResultat) lage = "ej";
      else if (d.harVarning) lage = "varning";
      else if (aktiv === "resultat") lage = "pa";
      else lage = "klar";
    } else if (steg.id === "schemaforslag") {
      if (!d.harResultat) lage = "ej";
      else if (d.schemaForslagGodkant) lage = "klar";
      else if (aktiv === "schemaforslag") lage = "pa";
      else lage = "ej";
    } else if (steg.id === "nyckeltal") {
      lage = aktiv === "nyckeltal" ? "pa" : "ej";
    }
    if (aktiv === steg.id && lage === "ej" && steg.id !== "fore") lage = "pa";
    if (aktiv === steg.id && lage === "klar") lage = "pa";
    return { id: steg.id, label: steg.label, lage, typ: steg.typ };
  });
}

export function behorighetEtikett(v: boolean | null | undefined) {
  if (v === true) return "Ja";
  if (v === false) return "Nej";
  return "Ej angivet";
}

export function behorighetLage(v: boolean | null | undefined): "ja" | "nej" | "okand" {
  return treVarde(v);
}

export const VERKSAMHET_UTAN_NAMN = "Verksamhet ej namngiven";

export function visningsNamnVerksamhet(org: string | null | undefined) {
  const n = String(org || "").trim();
  if (!n || n === "Ny verksamhet") return VERKSAMHET_UTAN_NAMN;
  return n;
}

export function genomsnittligSsgPct(medarbetare: { vakant?: boolean; grad?: number }[]) {
  const a = (medarbetare || []).filter((m) => !m.vakant);
  if (!a.length) return null;
  return a.reduce((s, m) => s + Number(m.grad || 0), 0) / a.length;
}

/** Faktisk använd kapacitet / tillgänglig SSG. Utan båda nämnarna finns inget utnyttjande. */
export function ssgUtnyttjandePct(anvandH: number | null | undefined, tillgangligSsgH: number | null | undefined) {
  if (anvandH == null || tillgangligSsgH == null || !(tillgangligSsgH > 0) || !Number.isFinite(anvandH)) return null;
  return (anvandH / tillgangligSsgH) * 100;
}

export function timmarEllerTomt(timmar: number | null | undefined) {
  if (timmar == null || !Number.isFinite(timmar)) return { text: "–", saknas: true as const };
  return { text: `${timmar.toLocaleString("sv-SE", { maximumFractionDigits: 1 })}\u00a0h`, saknas: false as const };
}

export function berakningsKallaText(kalla: "motor" | "lokal" | null | undefined) {
  if (kalla === "motor") return "Bemanningsbalans skapad med motor";
  if (kalla === "lokal") return "Förhandsberäkning i appen";
  return "Ingen beräkning är gjord ännu";
}

export function readinessFranApi(api: {
  underlag: () => {
    godkand: { kund: boolean; schema: boolean };
    sekoia: unknown;
    schema: unknown;
  };
  medarbetare: () => ReadinessMedarbetare[];
  underlagAndringar?: () => { kund?: boolean; medarbetare?: boolean };
}) {
  const u = api.underlag();
  const a = api.underlagAndringar?.() || {};
  return getBemanningsbalansReadiness({
    harKundrader: !!u.sekoia,
    harSchema: !!u.schema,
    kundGodkand: u.godkand.kund,
    kundAndradSedanGodkannande: !!a.kund,
    schemaGodkand: u.godkand.schema,
    medarbetareAndradSedanGodkannande: !!a.medarbetare,
    medarbetare: api.medarbetare(),
    defaultWorkTimeModelId: DEFAULT_WORK_TIME_MODEL_ID,
    workTimeModels: STANDARD_WORK_TIME_MODELS,
  });
}

export function processStegFranApi(
  api: Parameters<typeof readinessFranApi>[0] & {
    harBalans: () => boolean;
    regelbrott?: () => number;
  },
  aktivTab: string,
  extra?: { schemaForslagGodkant?: boolean },
) {
  const readiness = readinessFranApi(api);
  const lagenArg: Parameters<typeof processStegLagen>[0] = {
    aktivTab,
    readiness,
    harResultat: api.harBalans(),
    harVarning: (api.regelbrott?.() || 0) > 0,
  };
  if (extra?.schemaForslagGodkant !== undefined) lagenArg.schemaForslagGodkant = extra.schemaForslagGodkant;
  return processStegLagen(lagenArg);
}

/** Grönt bara när förändringen är bra för verksamheten – inte för allt som sjunker. */
export function jamforTon(opts: {
  namn: string;
  riktning: "upp" | "ner" | "lika";
  tackningSank: boolean;
}): "bra" | "varn" | "neutral" {
  if (opts.riktning === "lika") return "neutral";
  const namn = opts.namn.toLowerCase();
  const personalMinskning =
    namn.includes("personal") || namn.includes("schematid") || namn.includes("överbemanning") || namn.includes("överkapa");
  if (personalMinskning && opts.tackningSank) return "varn";
  if (opts.riktning === "upp") return "bra";
  if (namn.includes("täckt") || namn.includes("kundnära") || namn.includes("intäkt") || namn.includes("resultat"))
    return "varn";
  return "varn";
}

export function tomSummary() {
  return { ...TOM_SUMMARY };
}

export const MATCHNING_FORMEL = {
  täljare: "dimensionerandeResursbehovH − otacktDimensionerandeResursH",
  nämnare: "dimensionerandeResursbehovH",
  kod: "max(0, 1 - obemannatH / dimH) * 100",
  kalla: "modell.analysera: dimH = Σ dimensionerat×0,5 h; obemannatH = Σ max(0, dimensionerat−bemanning)×0,5 h",
  tidsmassigMatchning: true,
  overlapparTacktBehov: false,
  overlapparKundnara: false,
} as const;

export const UNDERKAPACITET_FORMEL = {
  falt: "obemannatH / otacktDimensionerandeResursH",
  kod: "Σ (dimensionerat − bemanning) × 0,5 h där dimensionerat > bemanning",
  kalla: "modell.analysera 30-minutersintervall mot dimensionerande kurva",
} as const;

export const OVERKAPACITET_FORMEL = {
  falt: "overkapacitetH",
  kod: "Σ (bemanning − rabehov) × 0,5 h där bemanning > rabehov",
  kalla: "modell.analysera 30-minutersintervall mot rått kundbehov (inte dimensionerat)",
  anvanderDimensionerandeKurva: false,
  asymmetriUtvarderasEfterAxelsberg: true,
} as const;

export function raknaSaknadeKompetenskrav(
  poster: { rule?: string; message?: string }[] | null | undefined,
) {
  return (poster || []).filter((w) => /kompetens|skill|delegering/i.test(`${w.rule || ""} ${w.message || ""}`)).length;
}

export function balansKanGodkannas(d: {
  tacktBehovPct: number | null | undefined;
  hardViolations: number;
  saknadeKompetenskrav?: number;
  jourResursbrist?: boolean;
}) {
  const reasons: string[] = [];
  if (d.jourResursbrist) {
    reasons.push("Schemat kan inte färdigställas utan ytterligare resurs.");
  }
  const tackt = d.tacktBehovPct;
  if (!d.jourResursbrist && (tackt == null || !(tackt >= 100 - 1e-6))) {
    reasons.push("Balans kan inte godkännas – kundbehov återstår att bemanna.");
  } else if (d.jourResursbrist && tackt != null && !(tackt >= 100 - 1e-6)) {
    reasons.push("Vissa kundinsatser är ännu inte bemannade.");
  }
  if (!d.jourResursbrist && (d.hardViolations || 0) > 0) {
    reasons.push("Balans kan inte godkännas – hårda regelbrott finns.");
  }
  if ((d.saknadeKompetenskrav || 0) > 0) {
    reasons.push("Balans kan inte godkännas – kompetens- eller behörighetskrav saknas.");
  }
  return { ok: reasons.length === 0, reasons };
}

export type GodkannVyIndata = {
  motorJobb?: { outcome?: string | null | undefined; stale?: boolean | undefined } | null | undefined;
  motorResultat?: unknown;
  tacktBehovPct?: number | null | undefined;
  hardViolations: number;
  saknadeKompetenskrav?: number;
  jourResursbrist?: boolean;
};

function motorGodkannKalla(d: GodkannVyIndata) {
  const summary = lasMotorSummary(d.motorResultat);
  const job = d.motorJobb;
  if (!summary || !job?.outcome) return null;
  const skillPoster = [...(summary.hardViolations || []), ...(summary.warnings || [])];
  return {
    outcome: String(job.outcome),
    stale: Boolean(job.stale),
    coveragePercent: summary.coveragePercent,
    hardViolations: (summary.hardViolations || []).length,
    saknadeKompetenskrav: raknaSaknadeKompetenskrav(skillPoster),
  };
}

/** Aktuellt motorresultat är canonical för Godkänn. Annars lokal gate. */
export function godkannBeslutFranVy(d: GodkannVyIndata) {
  const motor = motorGodkannKalla(d);
  if (motor) {
    const reasons: string[] = [];
    if (motor.stale) {
      reasons.push("Balansen bygger på ett tidigare underlag – skapa om Balans.");
    }
    if (motor.outcome === "kompletteras") {
      reasons.push("Schemat kan inte färdigställas utan ytterligare resurs.");
    } else if (motor.outcome !== "balans_klar") {
      reasons.push("Balans kan inte godkännas – beräkningen är inte klar.");
    }
    if (motor.outcome === "balans_klar" && !motor.stale) {
      if (motor.coveragePercent == null || !(motor.coveragePercent >= 100 - 1e-6)) {
        reasons.push("Balans kan inte godkännas – kundbehov återstår att bemanna.");
      }
      if ((motor.hardViolations || 0) > 0) {
        reasons.push("Balans kan inte godkännas – hårda regelbrott finns.");
      }
      if ((motor.saknadeKompetenskrav || 0) > 0) {
        reasons.push("Balans kan inte godkännas – kompetens- eller behörighetskrav saknas.");
      }
    }
    return { ok: reasons.length === 0, reasons, kalla: "motor" as const };
  }
  const lokal = balansKanGodkannas({
    tacktBehovPct: d.tacktBehovPct,
    hardViolations: d.hardViolations,
    ...(d.saknadeKompetenskrav != null ? { saknadeKompetenskrav: d.saknadeKompetenskrav } : {}),
    ...(d.jourResursbrist != null ? { jourResursbrist: d.jourResursbrist } : {}),
  });
  return { ...lokal, kalla: "lokal" as const };
}

export function hemHuvudCta(d: {
  lage: TidslageId;
  ready: boolean;
  godkannbar: boolean;
  balansGodkand?: boolean;
  pagaende?: boolean;
}) {
  if (d.pagaende) return { id: "status" as const, label: "Visa status", disabled: false };
  if (d.lage === "utfall") return { id: "utfall" as const, label: "Följ upp utfall", disabled: false };
  if (d.lage === "balans") {
    if (d.balansGodkand) return { id: "godkand" as const, label: "Balans godkänd", disabled: true };
    if (d.godkannbar) return { id: "godkann" as const, label: "Godkänn balans", disabled: false };
    return { id: "granska" as const, label: "Granska balans", disabled: false };
  }
  return { id: "skapa" as const, label: "Skapa balans", disabled: !d.ready };
}

export function hemStatusText(d: {
  lage: TidslageId;
  ready: boolean;
  blockingReasons: string[];
  godkannbar: boolean;
  balansGodkand?: boolean;
  tacktBehovPct?: number | null;
  pagaende?: boolean;
  klarForGranskning?: boolean;
}) {
  if (d.pagaende) return "Balans skapas";
  if (d.klarForGranskning && !d.godkannbar && !d.balansGodkand) return "Balans klar för granskning";
  if (d.lage === "utfall") return "Utfall kan följas upp";
  if (d.lage === "fore") return d.ready ? "Redo att skapa balans" : d.blockingReasons[0] || "Underlaget behöver kompletteras";
  if (d.balansGodkand) return "Balans godkänd";
  if (!d.godkannbar) return "Balansen behöver kompletteras";
  return "Redo att godkänna balans";
}

export function effektPilFranForandring(forandring: string): "upp" | "ner" | "lika" {
  const t = String(forandring || "").trim();
  if (!t || t === "–" || t === "-") return "lika";
  if (t.startsWith("−") || t.startsWith("-")) return "ner";
  if (t.startsWith("+")) return "upp";
  return "lika";
}

/** Pil följer talets riktning. Tecken tas bort så UI inte visar ↑ −36 h. */
export function visningEffekt(forandring: string) {
  const pil = effektPilFranForandring(forandring);
  const text = String(forandring || "").replace(/^[+\-−]\s*/, "").trim();
  if (pil === "lika") return { pil, text: forandring || "–" };
  return { pil, text: text || forandring };
}

/** Visa mål för kundnära tid bara om verksamheten har ett riktigt konfigurerat mål – inte pilotexemplet 75 %. */
export function konfigureratKundnaraMalPct(d: { varde?: number | null; definition?: string | null }) {
  if (d.varde == null || !Number.isFinite(Number(d.varde))) return null;
  const def = String(d.definition || "").toLowerCase();
  if (!def.trim() || /pilot|exempel|referens/.test(def)) return null;
  const n = Number(d.varde);
  return n <= 1.5 ? n * 100 : n;
}

export function behoverUppmarksamhet(d: {
  hardViolations: number;
  underkapacitetH: number;
  overkapacitetH: number;
  tacktBehovPct: number | null | undefined;
}) {
  const punkter: string[] = [];
  if ((d.hardViolations || 0) > 0) punkter.push(`${d.hardViolations} regelvarningar i befintligt schema`);
  if ((d.underkapacitetH || 0) > 0.05) punkter.push("underkapacitet vid vissa tider");
  if ((d.overkapacitetH || 0) > 0.05) punkter.push("överkapacitet vid andra tider");
  if (d.tacktBehovPct != null && d.tacktBehovPct < 100 - 1e-6) punkter.push("kundbehov inte fullt täckt");
  return punkter;
}

export const FORE_BALANS_NYCKLAR = [
  "Planerade personaltimmar",
  "Matchning mot behov",
  "Otäckt dimensionerande resursbehov",
  "Överbemanning",
  "Kundnära tid",
  "Täckt behov",
  "Personalkostnad",
  "Beräknad intäkt",
  "Ekonomiskt resultat",
] as const;

/** Bakåtkompatibelt alias – jämförelsen heter Före → Balans. */
export const FORE_EFTER_NYCKLAR = FORE_BALANS_NYCKLAR;

const FORE_BALANS_RUBRIK: Record<string, string> = {
  "Otäckt dimensionerande resursbehov": "Underkapacitet",
  Överbemanning: "Överkapacitet",
  "Beräknad intäkt": "Intäkt",
  "Ekonomiskt resultat": "Intäkt − schemakostnad",
};

export function filtreraJamforRader(
  tabell: { namn: string; fore: string; efter: string; forandring: string; riktning: "upp" | "ner" | "lika" }[],
) {
  const tillat = new Set<string>(FORE_BALANS_NYCKLAR);
  const ordning = FORE_BALANS_NYCKLAR as readonly string[];
  return tabell
    .filter((r) => tillat.has(r.namn))
    .sort((a, b) => ordning.indexOf(a.namn) - ordning.indexOf(b.namn))
    .map((r) => {
      const namn = FORE_BALANS_RUBRIK[r.namn] || r.namn;
      return {
        ...r,
        namn,
        underMatchning: namn === "Underkapacitet" || namn === "Överkapacitet",
        pil: effektPilFranForandring(r.forandring),
      };
    });
}

export function kundUnderlagStatus(d: { godkand: boolean; redigerad?: boolean; ofullstandig?: boolean }) {
  if (d.ofullstandig) return { kod: "kompletteras" as const, text: "Behöver kompletteras" };
  if (d.godkand && d.redigerad) return { kod: "forandrad" as const, text: "Förändrad sedan senaste godkännande" };
  if (d.godkand) return { kod: "klar" as const, text: "Klar" };
  return { kod: "kompletteras" as const, text: "Behöver kompletteras" };
}

export function oversiktVisaLage(d: { laddar?: boolean; fel?: string; tom?: boolean }) {
  if (d.laddar) return "laddar";
  if (d.fel) return "fel";
  if (d.tom) return "tom";
  return "klar";
}

export function kostnadPerTacktKundtimme(kostnadKr: number, tacktaKundtimmar: number) {
  if (!(tacktaKundtimmar > 0) || !Number.isFinite(kostnadKr)) return null;
  return kostnadKr / tacktaKundtimmar;
}
