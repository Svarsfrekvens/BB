/** Tolkar motorns resourceDiagnostics.jour. Ingen ny solverlogik. */

export type JourFonsterDiagnos = {
  date: string;
  start: string;
  end: string;
  matchingOpenJourShift?: boolean;
  status?: string;
};

export type JourDiagnos = {
  requiredJourSlots: number;
  coverableWithRegisteredStaff: number | null;
  minimumExternalJourSlots: number | null;
  jourCapacityShortfallDetected: boolean;
  externalDatesAreProvenUnique: boolean;
  blockingRules: string[];
  openJourShiftsInFore: { date?: string; start?: string; end?: string; matchingOpenJourShift?: boolean }[];
  uncoveredJourWindows: JourFonsterDiagnos[];
  userMessage: string;
  diagnosticExternalDates: string[];
};

/** Utkast för framtida explicit extra resurs – implementeras inte här. */
export const EXPLICIT_EXTERN_RESURS_FALT = [
  "antal",
  "tillgangligaDatum",
  "tillgangligaTider",
  "jourbehorighet",
  "nattbehorighet",
  "kompetens",
  "delegering",
  "helg",
  "timkostnad",
  "ssgEllerTimtak",
] as const;

export type ExplicitExternResursUtkast = {
  [K in (typeof EXPLICIT_EXTERN_RESURS_FALT)[number]]?: unknown;
};

function tal(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() && Number.isFinite(Number(v))) return Number(v);
  return null;
}

function somObjekt(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function falt(o: Record<string, unknown>, namn: string) {
  return o[namn];
}

export function lasJourDiagnos(raw: unknown): JourDiagnos | null {
  const rot = somObjekt(raw);
  if (!rot) return null;
  const nestlad = somObjekt(falt(rot, "jour"));
  const jour =
    nestlad ??
    (falt(rot, "requiredJourSlots") != null || falt(rot, "minimumExternalJourSlots") != null ? rot : null);
  if (!jour) return null;
  const minExt = tal(falt(jour, "minimumExternalJourSlots"));
  const req = tal(falt(jour, "requiredJourSlots")) ?? 0;
  const cov = tal(falt(jour, "coverableWithRegisteredStaff"));
  const open = Array.isArray(falt(jour, "openJourShiftsInFore")) ? (falt(jour, "openJourShiftsInFore") as unknown[]) : [];
  const windows = Array.isArray(falt(jour, "uncoveredJourWindows")) ? (falt(jour, "uncoveredJourWindows") as unknown[]) : [];
  const regler = falt(jour, "blockingRules");
  const datum = falt(jour, "diagnosticExternalDates");
  return {
    requiredJourSlots: req,
    coverableWithRegisteredStaff: cov,
    minimumExternalJourSlots: minExt,
    jourCapacityShortfallDetected: Boolean(falt(jour, "jourCapacityShortfallDetected")) || (minExt != null && minExt > 0),
    externalDatesAreProvenUnique: Boolean(falt(jour, "externalDatesAreProvenUnique")),
    blockingRules: Array.isArray(regler) ? regler.map(String) : [],
    openJourShiftsInFore: open.map((r) => {
      const o = somObjekt(r) || {};
      const rad: { date?: string; start?: string; end?: string; matchingOpenJourShift?: boolean } = {};
      if (falt(o, "date") != null) rad.date = String(falt(o, "date"));
      if (falt(o, "start") != null) rad.start = String(falt(o, "start"));
      if (falt(o, "end") != null) rad.end = String(falt(o, "end"));
      if (falt(o, "matchingOpenJourShift")) rad.matchingOpenJourShift = true;
      return rad;
    }),
    uncoveredJourWindows: windows.map((r) => {
      const o = somObjekt(r) || {};
      const rad: JourFonsterDiagnos = {
        date: String(falt(o, "date") || ""),
        start: String(falt(o, "start") || ""),
        end: String(falt(o, "end") || ""),
      };
      if (falt(o, "matchingOpenJourShift")) rad.matchingOpenJourShift = true;
      if (falt(o, "status") != null) rad.status = String(falt(o, "status"));
      return rad;
    }),
    userMessage: String(falt(jour, "userMessage") || ""),
    diagnosticExternalDates: Array.isArray(datum) ? datum.map(String) : [],
  };
}

export function lasJourDiagnosFranMotorSvar(svar: {
  resourceDiagnostics?: unknown;
  schemaJson?: string | null;
  preCheck?: unknown;
}): JourDiagnos | null {
  const direkt = lasJourDiagnos(svar.resourceDiagnostics);
  if (direkt) return direkt;
  if (!svar.schemaJson) return null;
  try {
    const schema = JSON.parse(svar.schemaJson) as Record<string, unknown>;
    return lasJourDiagnos(schema["resourceDiagnostics"]) ?? lasJourDiagnos(schema);
  } catch {
    return null;
  }
}

export type PrecheckRad = {
  code: string;
  severity?: string;
  message: string;
  date?: string;
  need?: number;
  available?: number;
};

export type Samtidighetsbrist = {
  date: string;
  need: number;
  available: number;
  tidstext: string;
  message: string;
};

function lasPrecheckLista(v: unknown): PrecheckRad[] {
  if (!Array.isArray(v)) return [];
  const ut: PrecheckRad[] = [];
  for (const rad of v) {
    const o = somObjekt(rad);
    if (!o) continue;
    const code = String(falt(o, "code") || "");
    if (!code) continue;
    const need = tal(falt(o, "need"));
    const available = tal(falt(o, "available"));
    const date = falt(o, "date") != null ? String(falt(o, "date")) : undefined;
    const row: PrecheckRad = {
      code,
      message: String(falt(o, "message") || ""),
    };
    if (falt(o, "severity") != null) row.severity = String(falt(o, "severity"));
    if (date) row.date = date;
    if (need != null) row.need = need;
    if (available != null) row.available = available;
    ut.push(row);
  }
  return ut;
}

export function lasPrecheck(raw: unknown): PrecheckRad[] {
  const rot = somObjekt(raw);
  if (!rot) return [];
  const direkt = lasPrecheckLista(falt(rot, "preCheck"));
  if (direkt.length) return direkt;
  const nestlad = somObjekt(falt(rot, "resourceDiagnostics"));
  if (nestlad) return lasPrecheckLista(falt(nestlad, "preCheck"));
  return [];
}

export function lasPrecheckFranMotorSvar(svar: {
  preCheck?: unknown;
  resourceDiagnostics?: unknown;
  schemaJson?: string | null;
}): PrecheckRad[] {
  const franFalt = lasPrecheckLista(svar.preCheck);
  if (franFalt.length) return franFalt;
  const franDiag = lasPrecheck(svar.resourceDiagnostics);
  if (franDiag.length) return franDiag;
  if (!svar.schemaJson) return [];
  try {
    const schema = JSON.parse(svar.schemaJson) as Record<string, unknown>;
    const franSchema = lasPrecheckLista(schema["preCheck"]);
    if (franSchema.length) return franSchema;
    return lasPrecheck(schema["resourceDiagnostics"]);
  } catch {
    return [];
  }
}

export function lasSamtidighetsbrist(rader: PrecheckRad[]): Samtidighetsbrist[] {
  const ut: Samtidighetsbrist[] = [];
  for (const r of rader) {
    if (r.code !== "INSUFFICIENT_TOTAL_CAPACITY") continue;
    const m = r.message.match(/(\d{4}-\d{2}-\d{2}).*?kl\.\s*([0-9:]+)–([0-9:]+).*?behov\s*=\s*(\d+).*?tillgängliga\s*=\s*(\d+)/i);
    const date = r.date || m?.[1] || "";
    const need = r.need ?? (m ? Number(m[4]) : null);
    const available = r.available ?? (m ? Number(m[5]) : null);
    if (!date || need == null || available == null) continue;
    const start = m?.[2];
    const end = m?.[3];
    ut.push({
      date,
      need,
      available,
      tidstext: start && end ? `${date} kl. ${start}–${end}` : date,
      message: r.message,
    });
  }
  return ut;
}

export function vakantaPassText(antal: number | null | undefined): string | null {
  if (antal == null || antal <= 0) return null;
  return `${antal} öppna Medvind-pass (Ingen placerad) räknas inte som personal. De skapar inte medarbetare och kan inte täcka jour eller kundbehov.`;
}

export function visaJourResursbrist(d: JourDiagnos | null | undefined): boolean {
  if (!d) return false;
  const n = d.minimumExternalJourSlots;
  return (n != null && n > 0) || d.jourCapacityShortfallDetected;
}

export function jourHuvudtext(d: JourDiagnos): string {
  const req = d.requiredJourSlots;
  const cov = d.coverableWithRegisteredStaff;
  const ext = d.minimumExternalJourSlots;
  if (req && cov != null && ext != null) {
    return `${req} jourpass behöver bemannas under perioden. Registrerad personal kan, efter redan arbetad jour och gällande jourtak, täcka högst ${cov}. Minst ${ext} jourpass behöver ytterligare resurs.`;
  }
  return d.userMessage || "Registrerad personal kan inte täcka obligatorisk jour under hela perioden.";
}

export function jourBindandeRegler(d: JourDiagnos): string[] {
  const ut: string[] = [];
  const rules = new Set(d.blockingRules.map((r) => r.toUpperCase()));
  if (rules.has("JOUR_4W") || rules.has("JOURFLOOR")) ut.push("48 h jour / 4 veckor");
  if (rules.has("JOUR_MONTH")) ut.push("50 h jour / månad");
  if (!ut.length) {
    ut.push("48 h jour / 4 veckor");
    ut.push("50 h jour / månad");
  }
  return [...new Set(ut)];
}

export function jourOpenForeText(d: JourDiagnos): string | null {
  const n = d.openJourShiftsInFore.length;
  if (!n && !d.uncoveredJourWindows.some((w) => w.matchingOpenJourShift)) return null;
  const antal = n || d.uncoveredJourWindows.filter((w) => w.matchingOpenJourShift).length;
  if (!antal) return null;
  return `${antal} öppna Jo-pass i Före saknar namngiven resurs. De är inte tillgänglig bemanning.`;
}

export type JourPanelModell = {
  visa: boolean;
  rubrik: string;
  ingress: string;
  huvud: string;
  jourpassBehov: number;
  mojligaMedRegistrerad: number | null;
  ytterligareJourpass: number | null;
  bindandeRegler: string[];
  openFore: string | null;
  datumOsakra: boolean;
  datumVarning: string | null;
  hardJourText: string;
  kundbristText: string;
  kompletteraCta: string;
  kompletteraHjalp: string;
  jourBristRad: string;
  samtidighetIngress: string;
};

export function jourPanelModell(d: JourDiagnos | null | undefined): JourPanelModell {
  const visa = visaJourResursbrist(d);
  const tom: JourPanelModell = {
    visa: false,
    rubrik: "Ytterligare jourresurs behövs",
    ingress: "Bemanningsbalans kan inte skapas fullt ut med registrerade resurser.",
    huvud: "",
    jourpassBehov: 0,
    mojligaMedRegistrerad: null,
    ytterligareJourpass: null,
    bindandeRegler: [],
    openFore: null,
    datumOsakra: true,
    datumVarning: null,
    hardJourText: "Schemat kan inte färdigställas utan ytterligare resurs.",
    kundbristText: "Vissa kundinsatser är ännu inte bemannade.",
    kompletteraCta: "Komplettera resurs",
    kompletteraHjalp:
      "BB har identifierat behovet. Du anger vilken faktisk resurs som finns tillgänglig.",
    jourBristRad: "",
    samtidighetIngress: "Samtidigt kundbehov överstiger tillgänglig bemanning vissa tider",
  };
  if (!visa || !d) return tom;
  const unika = d.externalDatesAreProvenUnique;
  const ext = d.minimumExternalJourSlots;
  return {
    ...tom,
    visa: true,
    huvud: jourHuvudtext(d),
    jourpassBehov: d.requiredJourSlots,
    mojligaMedRegistrerad: d.coverableWithRegisteredStaff,
    ytterligareJourpass: ext,
    bindandeRegler: jourBindandeRegler(d),
    openFore: jourOpenForeText(d),
    datumOsakra: !unika,
    datumVarning: unika
      ? null
      : "Vilka jourpass som behöver extern resurs beror på hur resterande jour fördelas.",
    jourBristRad: ext != null && ext > 0 ? `Jour: minst ${ext} pass saknar möjlig resurs` : tom.jourBristRad,
  };
}

export function harHardJourbrist(hardViolations: { rule?: string }[] | null | undefined, diagnos: JourDiagnos | null) {
  if (visaJourResursbrist(diagnos)) return true;
  return (hardViolations || []).some((v) => String(v.rule || "") === "JOUR_CAPACITY_SHORTFALL");
}

export function harMjukKundbrist(opts: {
  tacktBehovPct?: number | null | undefined;
  obemannadeAntal?: number | undefined;
  ofullstandigUtanSchema?: boolean | undefined;
}) {
  if (opts.ofullstandigUtanSchema) return false;
  if ((opts.obemannadeAntal || 0) > 0) return true;
  const t = opts.tacktBehovPct;
  return t != null && t < 100 - 1e-6;
}
