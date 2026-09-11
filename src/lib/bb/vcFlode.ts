/** Presentationsadapter för VC-flödet. Ingen ny beräkning av täckning, kostnad eller regler. */

export type ProcessStegLage = "ej" | "pa" | "klar" | "varning" | "blockerad";

export const PROCESS_STEG = [
  { id: "kundbehov", label: "Kundbehov" },
  { id: "medarbetare", label: "Medarbetare" },
  { id: "motor", label: "Skapa bemanningsbalans" },
  { id: "resultat", label: "Granska" },
  { id: "schemaforslag", label: "Godkänn" },
  { id: "nyckeltal", label: "Uppföljning" },
] as const;

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

export function skapaBalansHinder(d: {
  kundGodkand: boolean;
  schemaGodkand?: boolean;
  medarbetare: { namn: string; workTimeModelId?: string; nattbehorig?: boolean; vakant?: boolean }[];
  harUnderlag: boolean;
  blockerande?: string[];
}) {
  const skal: string[] = [];
  if (!d.harUnderlag) skal.push("Underlaget är inte inläst");
  if (!d.kundGodkand) skal.push("Kundbehovet är inte godkänt");
  const aktiva = (d.medarbetare || []).filter((m) => !m.vakant);
  const saknarModell = aktiva.filter((m) => !String(m.workTimeModelId || "").trim());
  if (saknarModell.length) skal.push(`${saknarModell.length} medarbetare saknar arbetstidsmodell`);
  if (aktiva.length && aktiva.every((m) => !m.nattbehorig)) skal.push("Nattbehörighet saknas");
  for (const b of d.blockerande || []) if (b) skal.push(b);
  return { aktiv: skal.length === 0 && d.harUnderlag && d.kundGodkand, skal };
}

export function processStegLagen(d: {
  aktivTab: string;
  kundGodkand: boolean;
  medarbetareOk: boolean;
  harResultat: boolean;
  harVarning: boolean;
  blockeradSkapa: boolean;
  godkandSchema?: boolean;
}): { id: string; label: string; lage: ProcessStegLage }[] {
  return PROCESS_STEG.map((steg) => {
    let lage: ProcessStegLage = "ej";
    if (steg.id === "kundbehov") lage = d.kundGodkand ? "klar" : d.aktivTab === "kundbehov" ? "pa" : "ej";
    else if (steg.id === "medarbetare") lage = d.medarbetareOk ? "klar" : d.aktivTab === "medarbetare" ? "pa" : "ej";
    else if (steg.id === "motor") {
      if (d.blockeradSkapa && !d.harResultat) lage = "blockerad";
      else if (d.harResultat) lage = "klar";
      else if (d.aktivTab === "motor") lage = "pa";
      else lage = "ej";
    } else if (steg.id === "resultat") {
      if (!d.harResultat) lage = "ej";
      else if (d.harVarning) lage = "varning";
      else lage = d.aktivTab === "resultat" ? "pa" : "klar";
    } else if (steg.id === "schemaforslag") {
      if (!d.harResultat) lage = "ej";
      else if (d.godkandSchema) lage = "klar";
      else lage = d.aktivTab === "schemaforslag" ? "pa" : "ej";
    } else if (steg.id === "nyckeltal") {
      lage = d.aktivTab === "nyckeltal" ? "pa" : d.harResultat ? "ej" : "ej";
    }
    if (d.aktivTab === steg.id && lage === "ej") lage = "pa";
    if (d.aktivTab === steg.id && lage === "klar") lage = "pa";
    return { id: steg.id, label: steg.label, lage };
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
