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
  };
  if (!visa || !d) return tom;
  const unika = d.externalDatesAreProvenUnique;
  return {
    ...tom,
    visa: true,
    huvud: jourHuvudtext(d),
    jourpassBehov: d.requiredJourSlots,
    mojligaMedRegistrerad: d.coverableWithRegisteredStaff,
    ytterligareJourpass: d.minimumExternalJourSlots,
    bindandeRegler: jourBindandeRegler(d),
    openFore: jourOpenForeText(d),
    datumOsakra: !unika,
    datumVarning: unika
      ? null
      : "Vilka jourpass som behöver extern resurs beror på hur resterande jour fördelas.",
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
