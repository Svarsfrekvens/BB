/** Presentationsadapter för VC-flödet. Ingen ny beräkning av täckning, kostnad eller regler. */

export type ProcessStegLage = "ej" | "pa" | "klar" | "varning" | "blockerad";

export const PROCESS_STEG = [
  { id: "kundbehov", label: "Kundbehov" },
  { id: "medarbetare", label: "Medarbetare" },
  { id: "skapa", label: "Skapa bemanningsbalans" },
  { id: "resultat", label: "Granska" },
  { id: "foreefter", label: "Före och efter" },
  { id: "schemaforslag", label: "Godkänn" },
  { id: "nyckeltal", label: "Uppföljning" },
] as const;

export const TACKT_BEHOV_FORKLARING =
  "Täckt behov = bemannat kundbehov / totalt kundbehov.";
export const KUNDNARA_FORKLARING =
  "Kundnära tid = schemalagd kundnära arbetstid / total schemalagd arbetstid.";
export const KAPACITET_FORKLARING =
  "Överkapacitet betyder att bemanning finns när behovet är lägre. Underkapacitet betyder att kundbehov saknar motsvarande bemanning vid andra tider.";
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

export const TRE_OMRADEN_RUBRIKER = ["Kundnytta", "Hållbar bemanning", "Rätt resurser i rätt tid"] as const;

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
export function vcStatusText(status: string | null | undefined) {
  const s = String(status || "").toUpperCase();
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
  const s = o.summary;
  if (s && typeof s === "object") {
    const x = s as Record<string, unknown>;
    return {
      status: String(x.status || o.solverStatus || "NOT_RUN"),
      coveragePercent: typeof x.coveragePercent === "number" ? x.coveragePercent : null,
      customerNearPercent: typeof x.customerNearPercent === "number" ? x.customerNearPercent : null,
      cost: Number(x.cost || 0),
      hardViolations: Array.isArray(x.hardViolations) ? (x.hardViolations as MotorUiSummary["hardViolations"]) : [],
      warnings: Array.isArray(x.warnings) ? (x.warnings as MotorUiSummary["warnings"]) : [],
      changedShiftCount: Number(x.changedShiftCount || 0),
      lockedShiftCount: Number(x.lockedShiftCount || 0),
      explanationSummary: String(x.explanationSummary || ""),
      performanceSummary: String(x.performanceSummary || ""),
    };
  }
  if (typeof o.solverStatus === "string" || typeof o.explanation === "string") {
    return {
      ...TOM_SUMMARY,
      status: String(o.solverStatus || "NOT_RUN"),
      explanationSummary: String(o.explanation || "").split(".")[0],
      changedShiftCount: Array.isArray(o.forandringar) ? o.forandringar.length : 0,
    };
  }
  return null;
}

export type DelStatus = "ej" | "kompletteras" | "klar" | "forandrad";

export type ReadinessMedarbetare = {
  namn: string;
  vakant?: boolean;
  workTimeModelId?: string;
  nattbehorig?: boolean | null;
  jour?: boolean | null;
};

export type BemanningsbalansReadinessIndata = {
  harKundrader: boolean;
  harSchema: boolean;
  kundGodkand: boolean;
  kundAndradSedanGodkannande?: boolean;
  schemaGodkand: boolean;
  medarbetareAndradSedanGodkannande?: boolean;
  medarbetare: ReadinessMedarbetare[];
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

export function getBemanningsbalansReadiness(d: BemanningsbalansReadinessIndata): BemanningsbalansReadiness {
  const blockingReasons: string[] = [];
  const warnings: string[] = [];
  const aktiva = (d.medarbetare || []).filter((m) => !m.vakant);
  const harMedarbetare = aktiva.length > 0;
  const harKunddata = !!d.harKundrader;
  const saknarModell = aktiva.filter((m) => !String(m.workTimeModelId || "").trim());

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
}) {
  const r = getBemanningsbalansReadiness({
    harKundrader: d.harKundrader ?? d.harUnderlag,
    harSchema: d.harSchema ?? d.harUnderlag,
    kundGodkand: d.kundGodkand,
    kundAndradSedanGodkannande: d.kundAndradSedanGodkannande,
    schemaGodkand: !!d.schemaGodkand,
    medarbetareAndradSedanGodkannande: d.medarbetareAndradSedanGodkannande,
    medarbetare: d.medarbetare,
  });
  const skal = [...r.blockingReasons, ...(d.blockerande || []).filter(Boolean)];
  return { aktiv: skal.length === 0, skal, warnings: r.warnings, delar: r.delar };
}

export function processStegLagen(d: {
  aktivTab: string;
  readiness: BemanningsbalansReadiness;
  harResultat: boolean;
  harVarning: boolean;
  schemaForslagGodkant?: boolean;
}): { id: string; label: string; lage: ProcessStegLage }[] {
  const tabAlias = d.aktivTab === "motor" ? "skapa" : d.aktivTab;
  return PROCESS_STEG.map((steg) => {
    let lage: ProcessStegLage = "ej";
    if (steg.id === "kundbehov") {
      if (d.readiness.delar.kund === "klar") lage = "klar";
      else if (d.readiness.delar.kund === "forandrad") lage = "varning";
      else if (d.readiness.delar.kund === "kompletteras" || tabAlias === "kundbehov") lage = "pa";
      else lage = "ej";
    } else if (steg.id === "medarbetare") {
      if (!d.readiness.harMedarbetare) lage = "ej";
      else if (d.readiness.delar.medarbetare === "klar") lage = "klar";
      else if (d.readiness.delar.medarbetare === "forandrad") lage = "varning";
      else if (d.readiness.delar.medarbetare === "kompletteras") lage = tabAlias === "medarbetare" ? "pa" : "ej";
      else lage = tabAlias === "medarbetare" ? "pa" : "ej";
    } else if (steg.id === "skapa") {
      if (!d.readiness.ready && !d.harResultat) lage = "blockerad";
      else if (d.harResultat) lage = "klar";
      else if (tabAlias === "skapa") lage = "pa";
      else lage = "ej";
    } else if (steg.id === "resultat") {
      if (!d.harResultat) lage = "ej";
      else if (d.harVarning) lage = "varning";
      else lage = tabAlias === "resultat" ? "pa" : "klar";
    } else if (steg.id === "foreefter") {
      if (!d.harResultat) lage = "ej";
      else lage = tabAlias === "foreefter" ? "pa" : "klar";
    } else if (steg.id === "schemaforslag") {
      if (!d.harResultat) lage = "ej";
      else if (d.schemaForslagGodkant) lage = "klar";
      else lage = tabAlias === "schemaforslag" ? "pa" : "ej";
    } else if (steg.id === "nyckeltal") {
      lage = tabAlias === "nyckeltal" ? "pa" : "ej";
    }
    if (tabAlias === steg.id && lage === "ej") lage = "pa";
    if (tabAlias === steg.id && lage === "klar") lage = "pa";
    return { id: steg.id, label: steg.label, lage };
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
  return processStegLagen({
    aktivTab,
    readiness,
    harResultat: api.harBalans(),
    harVarning: (api.regelbrott?.() || 0) > 0,
    schemaForslagGodkant: extra?.schemaForslagGodkant,
  });
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

export const FORE_EFTER_NYCKLAR = [
  "Täckt behov",
  "Kundnära tid",
  "Personalkostnad",
  "Ekonomiskt resultat",
  "Överbemanning",
  "Obemannat kundbehov",
] as const;

const FORE_EFTER_RUBRIK: Record<string, string> = {
  Personalkostnad: "Schemakostnad",
  "Ekonomiskt resultat": "Intäkt − schemakostnad",
  Överbemanning: "Överkapacitet",
  "Obemannat kundbehov": "Underkapacitet",
};

export function filtreraJamforRader(
  tabell: { namn: string; fore: string; efter: string; forandring: string; riktning: "upp" | "ner" | "lika" }[],
) {
  const tillat = new Set<string>(FORE_EFTER_NYCKLAR);
  return tabell
    .filter((r) => tillat.has(r.namn))
    .map((r) => ({ ...r, namn: FORE_EFTER_RUBRIK[r.namn] || r.namn }));
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
