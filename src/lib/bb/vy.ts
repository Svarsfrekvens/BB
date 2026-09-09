/* ------------------------------------------------------------------ *
 * Bro för innehållsvyerna. Beräkningslagret (src/lib/bb/app.ts) räknar
 * precis som förut och publicerar sitt resultat här. React-vyerna läser
 * samma data och sköter enbart utseendet – ingen innerHTML.
 * ------------------------------------------------------------------ */

/** Appens version – ändras bara här. */
export const APP_VERSION = "3.0";

/** Flikar som ritas av React. Övriga ritas ännu av det gamla lagret. */
export const REAKT_TABS = new Set<string>(["hem", "uppladdning", "verksamhet", "kundgrupp", "schemafil", "medarbetare", "underlag", "foreefter", "schemaforslag", "oversikt", "kundbehov", "resurskurva", "personal", "schema", "nyckeltal", "ekonomi", "kunder", "atgarder", "kontroller", "intakter", "simulering", "villkor", "installningar", "sprid", "motor"]);

import type { DatumPass } from "./medvind";
import type { Lage, JamforRad, Flytt, SchemaForandring, SchemaVarning } from "./modell";

export type Underlag = {
  godkand: { kund: boolean; schema: boolean; allt: boolean };
  schema: {
    filnamn: string; blad: string; medarbetare: number; vakanta: number; vikarier: number; pass: number;
    veckor: number; timmar: number; jour: number; vakantaPass: number;
  } | null;
  sekoia: { insatser: number; kunder: number; from: string; to: string; timmar: number } | null;
  period: { from: string; to: string; dagar: number };
  villkor: { regel: string; varde: string }[];
  balans: { flyttade: number; skapad: string } | null;
  vikarie: { antalBorttagna: number; antalBehalls: number } | null;
  varningar: string[];
};

export type SparadInfo = {
  period: string;
  insatser: number;
  kunder: number;
  medarbetare: number;
  pass: number;
  balans: boolean;
  uppdaterad: string | null;
};

export type Medarbetare = {
  namn: string;
  vakant: boolean;
  vikarie: boolean;
  grad: number;
  samordnare: boolean;
  delegering: boolean;
  jour: boolean;
  nattbehorig: boolean;
  passprofil: string;
  helg: string;
  tidigastStart: string;
  senastSlut: string;
  maxDagarIFoljd: number;
  franvaro: string;
  timkostnad: number;
  anstallning: string;
};

export type VikarieBeslut = {
  id: string; namn: string; datum: string; start: string; slut: string; timmar: number; behovs: boolean;
};

export type ForeEfter = {
  fore: Lage;
  efter: Lage | null;
  tabell: JamforRad[];
  punkter: string[];
  flyttade: Flytt[];
  minska: string[];
  forstark: string[];
  vikarie: { antalBorttagna: number; antalBehalls: number } | null;
  varningar: string[];
};


import type {
  BladRad,
  KundLek,
  Mote,
  SimBas,
  SimResultat,
  SpridInsats,
  VillkorModell,
  VillkorRad,
  Insats,
  PendingImport,
  PendingMeta,
  SchemaModell,
  VyData,
  VyTillstand,
} from "./typer";

export type VyApi = {
  h1: (x: number) => string;
  kr: (x: number) => string;
  ber: (namn: string) => number | string | null;
  hasBer: () => boolean;
  harSchema: () => boolean;
  underlag: () => Underlag;
  valjSchemaFil: () => void;
  hanteraSchemaFil: (f: File) => void;
  medarbetare: () => Medarbetare[];
  sparadInfo: () => SparadInfo | null;
  utfall: () => {
    antal: number; utford: number; installd: number; flyttad: number; ejUtford: number; ovrigt: number;
    medUtford: number; inomFonsterPct: number | null; snittAvvikelseMin: number | null;
  } | null;
  harUnderlag: () => boolean;
  rensaUnderlag: () => void;
  vikarieBeslut: () => VikarieBeslut[];
  schemaForandringar: () => SchemaForandring[];
  schemaVarningar: () => SchemaVarning[];
  schematidKalla: () => "medvind" | "sekoia";
  /** Reglerna ur Styrande villkor i optimeringsmotorns format. */
  motorRegler: () => {
    minRestHours: number;
    maxWeeklyHours: number;
    maxShiftHours: number;
    maxConsecutiveDays: number;
    nightFloor: number;
    flexibilityStep: number;
  };
  motorResultat: () => Record<string, unknown> | null;
  berakningsKalla: () => "motor" | "lokal" | null;
  anvandMotorResultat: (res: unknown) => boolean;
  schemaPassOriginal: () => DatumPass[];

  medarbetareSet: (namn: string, falt: string, varde: unknown) => void;
  medarbetareLaggTill: (namn: string) => void;
  rensaSchemaOriginal: () => void;
  skapaBalans: () => void;
  aterstallBalans: () => void;
  harBalans: () => boolean;
  foreEfter: () => ForeEfter | null;
  foreLage: () => (Lage & { kundnaraAndel: number; schemakostnad: number }) | null;
  schemaPass: () => DatumPass[];
  regelbrott: () => number;
  arbetsRader: () => Insats[];
  cellToIso: (v: unknown) => string | null;
  addDays: (iso: string, n: number) => string;
  setTab: (id: string) => void;
  setDagar: (n: number) => void;
  skapa: () => void;
  valjFil: () => void;
  gfpKunder: () => string[];
  veckodagIdx: (iso: string) => number;
  kundEditSet: (id: string, falt: string, varde: unknown) => void;
  kundEditTaBort: (id: string) => void;
  kundToggleVeckodag: (id: string, dag: number) => void;
  kundEditLaggTill: (iso: string) => void;
  kundLaggTillNy: (namn: string, iso: string) => void;
  laggTillGenomforandeplan: (kund: string) => number;
  aterstallKundEdit: () => void;
  curveDag: () => number;
  setCurveDag: (n: number) => void;
  clockMin: (c: string) => number | null;
  schemaPerSlot: (iso: string) => number[] | null;
  harPersonal: () => boolean;
  personalRader: () => BladRad[];
  personalEditAktiv: () => boolean;
  personalSet: (id: string, falt: string, varde: unknown) => void;
  personalTaBort: (id: string) => void;
  personalLaggTillFran: (data: Record<string, unknown>) => void;
  aterstallPersonalEdit: () => void;
  schemaModell: () => SchemaModell | null;
  flyttaPass: (passId: string, namn: string) => void;
  aterstallSchema: () => void;
  planDays: () => number;
  berDef: (namn: string) => string;
  setActiveVerks: (id: string) => void;
  addVerks: () => void;
  taBortVerks: (id: string) => void;
  hanteraFil: (f: File) => void;
  godkannImport: () => void;
  godkannKund: () => void;
  godkannSchema: () => void;
  avbrytImport: () => void;
  chatFraga: (text: string) => string;
  harIntakter: () => boolean;
  intaktRader: () => BladRad[];
  intaktEditAktiv: () => boolean;
  intaktSetGrund: (kund: string, krPerDygn: number | string) => void;
  intaktSetAktiv: (kund: string, aktiv: boolean) => void;
  aterstallIntaktEdit: () => void;
  simBase: () => SimBas;
  simResultat: () => SimResultat;
  simVarden: () => Record<string, number>;
  simSet: (id: string, v: number) => void;
  simReset: () => void;
  villkor: () => VillkorModell | null;
  vardeMedEnhet: (r: VillkorRad) => string;
  avidentifieraEtt: (namn: string) => string;
  setOrg: (v: string) => void;
  setTal: (key: string, varde: number | string) => void;
  rensaAllt: () => void;
  minClock: (m: number) => string;
  spridDagIdx: () => number;
  setSpridDag: (n: number) => void;
  spridZoom: () => string;
  setSpridZoom: (z: string) => void;
  kundLek: () => KundLek;
  kundDagModell: (iso: string) => SpridInsats[];
  kundDagKurva: (ins: SpridInsats[], moten: Mote[]) => { slots: number[]; peak: number; peakSlot: number };
  flyttaInsats: (insId: string, iso: string, mins: number) => void;
  flyttaMote: (idx: number, mins: number) => void;
  laggMote: (iso: string) => void;
  aterstallSprid: () => void;
  /** Kopia av arbetskopiorna, för Ångra efter en borttagning. */
  ogonblicksbild: () => string;
  aterstallOgonblicksbild: (snap: string) => void;
  [key: string]: unknown;
};

export type VyVerks = { id: string; org: string; filled: boolean };

export type VyState = {
  tab: string;
  verks: VyVerks[];
  aktivVerks: string;
  maxVerks: number;
  pending: PendingImport | null;
  pendingMeta: PendingMeta | null;
  /** Sant medan en fil läses in – visar "Läser in…". */
  laser: boolean;
  d: VyData | null;
  state: VyTillstand | null;
  api: VyApi | null;
  nonce: number;
};

let vy: VyState = { tab: "oversikt", verks: [], aktivVerks: "", maxVerks: 4, pending: null, pendingMeta: null, laser: false, d: null, state: null, api: null, nonce: 0 };
const lyssnare = new Set<() => void>();

export function publiceraVy(delar: Partial<VyState>) {
  vy = { ...vy, ...delar, nonce: vy.nonce + 1 };
  lyssnare.forEach((f) => f());
}

export const bbVy = {
  subscribe(f: () => void) {
    lyssnare.add(f);
    return () => {
      lyssnare.delete(f);
    };
  },
  get(): VyState {
    return vy;
  },
};

/** Standardprops för en innehållsvy. */
export type VyProps = { d: VyData | null; state: VyTillstand; api: VyApi };

/* ---------- Centralt talformat (bara utseende, ingen beräkning) ---------- */

const en = (x: number) => (Number.isFinite(x) ? x : 0).toLocaleString("sv-SE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Procent med en decimal och hårt mellanslag före tecknet: 88,0 %. */
export const fmtPct = (x: number) => `${en(x)}\u00a0%`;
/** Timmar med en decimal: 1 142,1 h. */
export const fmtH = (x: number) => `${en(x)}\u00a0h`;
/** Kronor utan decimaler med tusentalsavgränsning: 460 000 kr. */
export const fmtKr = (x: number) => `${Math.round(Number.isFinite(x) ? x : 0).toLocaleString("sv-SE")}\u00a0kr`;
