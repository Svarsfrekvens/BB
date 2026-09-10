/* ------------------------------------------------------------------ *
 * Bro mellan beräkningslagret (src/lib/bb/app.ts, oförändrat) och
 * React-skalet. Logiken publicerar ett "skal"-tillstånd som
 * React-komponenterna läser – ingen innerHTML för navigation och topprad.
 * ------------------------------------------------------------------ */

export type SkalTab = {
  id: string;
  label: string;
  ic: string;
  grupp: string;
  /** Undertext i menyn. */
  sub?: string;
  /** Sant när fliken är låst tills föregående steg är klart. */
  last?: boolean;
  /** Sant när steget är genomfört (visar bock). */
  klar?: boolean;
};
export type SkalSteg = { id: string; label: string };

export type SkalDemo = { rubrik: string; text: string; nr: number; av: number };

export type SkalState = {
  tabs: SkalTab[];
  grupper: string[];
  tab: string;
  avanceratOppen: boolean;
  eyebrow: string;
  titel: string;
  org: string;
  periodFoot: string;
  optimerat: boolean;
  steg: SkalSteg[];
  stegIdx: number;
  demo: SkalDemo | null;
  /** Sant när det finns ändringar som inte exporterats. */
  osparat: boolean;
  /** Versionsstämpel som visas i sidfoten. */
  version: string;
};

let skal: SkalState = {
  tabs: [],
  grupper: [],
  tab: "oversikt",
  avanceratOppen: false,
  eyebrow: "Översikt",
  titel: "Bemanningsbalans",
  org: "Ny verksamhet",
  periodFoot: "",
  optimerat: false,
  steg: [],
  stegIdx: -1,
  demo: null,
  osparat: false,
  version: "",
};

const lyssnare = new Set<() => void>();

export function publiceraSkal(delar: Partial<SkalState>) {
  skal = { ...skal, ...delar };
  lyssnare.forEach((f) => f());
}

export type SkalActions = {
  setTab: (id: string) => void;
  toggleAvancerat: () => void;
  skapa: () => void;
  borjaOm: () => void;
  demo: () => void;
  exportera: () => void;
  stoppaDemo: () => void;
};

export const bbSkal = {
  subscribe(f: () => void) {
    lyssnare.add(f);
    return () => {
      lyssnare.delete(f);
    };
  },
  get(): SkalState {
    return skal;
  },
  actions: {
    setTab: () => {},
    toggleAvancerat: () => {},
    skapa: () => {},
    borjaOm: () => {},
    demo: () => {},
    exportera: () => {},
    stoppaDemo: () => {},
  } as SkalActions,
};
