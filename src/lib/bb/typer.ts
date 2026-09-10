/* ------------------------------------------------------------------ *
 * Typer för presentationslagret. Beräkningslagret (app.ts/core.ts) är
 * oförändrat – här beskriver vi bara formen på det data vyerna läser,
 * så att komponenterna slipper any.
 * ------------------------------------------------------------------ */

/** Rad ur ett inläst Excel-blad: kolumnnamn → värde. */
export type BladRad = Record<string, unknown>;

/** En insatsrad ur kundbehovet. */
export type Insats = {
  kallrad?: number;
  _id?: string;
  datum: string;
  kund: string;
  insats: string;
  start: string;
  slut?: string;
  fonsterSlut?: string;
  minuter: number;
  tvaPersoner?: boolean;
  flyttbar?: boolean;
  status?: string;
  veckodagar?: number[];
  [falt: string]: unknown;
};

/** Summering per kund. */
export type KundSummering = {
  kund: string;
  insatser: number;
  kundbehovH: number;
  personalbehovH?: number;
  [falt: string]: unknown;
};

/** Ett 30-minutersintervall i resurskurvan. */
export type KurvSlot = {
  datum: string;
  klockan: string;
  rabehov: number;
  medNattgolv: number;
  dimensionerat: number;
  resursMin?: number;
  natt?: boolean;
};

export type Resurskurva = {
  intervall: KurvSlot[];
  topp: { rabehov: number; datum: string | null; klockan: string | null; dimensionerat: number };
  rattResursbehovTotH: number;
  dimensionerandeDirektResursbehovH: number;
  [falt: string]: unknown;
};

export type Nyckeltal = {
  kundbehovH: number;
  personalbehovH: number;
  antalInsatser: number;
  dubbelbemannadeRader: number;
  extraDubbelH: number;
  [falt: string]: unknown;
};

export type Ekonomital = {
  planeradKostnad: number;
  planeradOverkapacitetH: number;
  [falt: string]: unknown;
};

/** Beräknat underlag för aktuell period – det vyerna kallar `d`. */
export type VyData = {
  from: string;
  rows: Insats[];
  kunder: KundSummering[];
  gem?: { kundbehovH: number } | null;
  n: Nyckeltal;
  curve: Resurskurva;
  eco: Ekonomital;
  resursH: number;
  redigerad?: boolean;
  fil?: { hours?: number; peak: { value: number; datum: string; tid: string } } | null;
  [falt: string]: unknown;
};

/** Kontrollrad ur Datakontroller/Åtgärder. */
export type Kontroll = {
  kontroll: string;
  utfall?: unknown;
  forvantat?: unknown;
  status: string;
  atgard?: string;
};

/** Villkorsrad ur HR-bladen. */
export type VillkorRad = { namn: string; varde: unknown; enhet?: string; [falt: string]: unknown };

export type VillkorModell = {
  installningar: VillkorRad[];
  individ: BladRad[];
  rorligaKategorier?: Record<string, string[]>;
  rorligaAntal?: number;
  [falt: string]: unknown;
};

/* ---------- Schema ---------- */

export type Pass = { id: string; namn: string; datum: string; typ: string; start: string; slut: string; timmar?: number };

export type SchemaVarning = { text: string; indikation?: boolean };

export type SchemaModell = {
  model: {
    medarbetare: string[];
    dagar: string[];
    prof: Record<string, { nattbehorig?: boolean; [falt: string]: unknown }>;
    [falt: string]: unknown;
  };
  effektiva: Pass[];
  varningar: Record<string, SchemaVarning[]>;
  medInfo: Record<string, { diff: number; nattbehorig?: boolean }>;
  moves: Record<string, string>;
  notis: { ton: string; namn: string; text: string } | null;
};

/* ---------- Sprid behov ---------- */

export type SpridInsats = {
  id: string;
  kund: string;
  insats: string;
  dur: number;
  tidigast: number | null;
  senast: number | null;
  slack: number;
  flyttbar: boolean;
  staff: number;
  start: number;
  end: number;
  fonsterStart: number | null;
  fonsterEnd: number | null;
  original: number | null;
  moved: boolean;
};

export type Mote = { datum: string; titel: string; start: number; dur: number; personal: number };

export type KundLek = { moves: Record<string, number>; moten: Mote[] };

/* ---------- Tillstånd ---------- */

export type Period = { from: string; to?: string };

/** Appens tillstånd – de fält presentationslagret läser. */
export type VyTillstand = {
  org?: string;
  period?: Period | null;
  optimerat?: boolean;
  analysisDays: number;
  importDays: number;
  planDays: number;
  plannedHours: number;
  hourlyCost?: number;
  budget: number;
  absencePct: number;
  reservePct: number;
  kontroller?: Kontroll[] | null;
  individschema?: { rows: BladRad[] } | null;
  personal?: { rows: BladRad[] } | null;
  intakter?: { rows: BladRad[] } | null;
  villkor?: VillkorModell | null;
  kundLek?: KundLek | null;
  __gfpKund?: string;
  [falt: string]: unknown;
};

/* ---------- Import ---------- */

export type ImportKund = { kund: string; insatser: number; kundbehovH: number };
export type ImportAvvisad = { kallrad: number; orsak: string };

export type ImportSummering = { count: number; kundbehovH: number; personalbehovH: number };

export type PendingImport = {
  blockera?: boolean;
  varningar: string[];
  avvisade: ImportAvvisad[];
  timmarPerKund: ImportKund[];
  lastaRader: number;
  godkandaRader: number;
  avvisadeRader: number;
  antalKunder: number;
  antalGemensamma: number;
  antalFasta: number;
  antalFlyttbara: number;
  antalDubbelbemannade: number;
  kundbehovH: number;
  personalbehovH: number;
  from: string;
  to: string;
  days: number;
  first28: (ImportSummering & { from: string; to: string }) | null;
};

export type PendingMeta = {
  sheet: string;
  headerRow: number;
  fileName: string;
  [blad: string]: unknown;
};

/* ---------- Vad händer om ---------- */

export type Vakans = { namn: unknown; timmar: number; kostnad: number };

export type SimBas = {
  schematid: number;
  timkostnad: number;
  budget: number;
  reservPct: number;
  korttidPct: number;
  buffertPct: number;
  intakt: number;
  vak: Vakans[];
  kundRate: Record<string, number>;
  kundDagar: Record<string, number>;
  dagar: number;
  dimBehov: number;
  nattgolv: number;
  planeradeTimmar: number;
  malPct: number;
};

export type SimResultat = {
  timkostnad: number;
  schematid: number;
  schemakostnad: number;
  korttidKr: number;
  buffertKr: number;
  totalPrognos: number;
  reservKr: number;
  budgetavvikelse: number;
  disponibelt: number;
  intakt: number;
  dimBehov: number;
  gapH: number;
  gapKr: number;
  planeradeTimmar: number;
  malPct: number;
  extraTimmar: number;
  tillsattVak: number;
  resultat: number;
};
