/** Vad Börja om ska lämna kvar. Ingen beräkning. */

export const BORJA_OM_STARTLAGE = "start" as const;
export const BORJA_OM_TAB = "hem" as const;

export type Arbetsminne = {
  rows?: unknown[];
  period?: unknown;
  schemaOriginal?: unknown;
  balans?: unknown;
  motorResultat?: unknown;
  motorJobb?: unknown;
  extraResurser?: unknown[];
  optimerat?: boolean;
  balansGodkand?: boolean;
  kundGodkand?: boolean;
  schemaGodkand?: boolean;
  kundAndrad?: boolean;
  medarbetareAndrad?: boolean;
  jamfor?: unknown;
  nyttSchema?: unknown;
  kundEdit?: unknown;
  schemaLek?: unknown;
};

export function nollstalltArbetsminne(): Required<Pick<
  Arbetsminne,
  | "rows"
  | "period"
  | "schemaOriginal"
  | "balans"
  | "motorResultat"
  | "motorJobb"
  | "extraResurser"
  | "optimerat"
  | "balansGodkand"
  | "kundGodkand"
  | "schemaGodkand"
  | "kundAndrad"
  | "medarbetareAndrad"
  | "jamfor"
  | "nyttSchema"
  | "kundEdit"
  | "schemaLek"
>> {
  return {
    rows: [],
    period: null,
    schemaOriginal: null,
    balans: null,
    motorResultat: null,
    motorJobb: null,
    extraResurser: [],
    optimerat: false,
    balansGodkand: false,
    kundGodkand: false,
    schemaGodkand: false,
    kundAndrad: false,
    medarbetareAndrad: false,
    jamfor: null,
    nyttSchema: null,
    kundEdit: null,
    schemaLek: null,
  };
}

export function harKvarvarandeArbete(s: Arbetsminne | null | undefined) {
  if (!s) return false;
  return Boolean(
    s.balans ||
      s.motorResultat ||
      s.motorJobb ||
      s.schemaOriginal ||
      s.optimerat ||
      (Array.isArray(s.rows) && s.rows.length) ||
      (Array.isArray(s.extraResurser) && s.extraResurser.length),
  );
}
