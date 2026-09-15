/* ------------------------------------------------------------------ *
 * Delar en lång period i körningsfönster som optimeringsmotorn klarar.
 * Ingen beräkning av behov sker här – bara uppdelning av redan byggd
 * data i datumordning.
 * ------------------------------------------------------------------ */

/** Motorns check_input: max 4000 insatser, period 1–42 dagar. Pilot: ett fönster upp till 28 dagar. */
export const MOTOR_MAX_INSATSER = 4000;
export const HELPERIOD_MAX_DAGAR = 28;

/** Tidigare klientskydd. Används om ett enda fönster blir för stort. */
export const SMALA_FONSTER_MAX_INSATSER = 320;
export const SMALA_FONSTER_MAX_DAGAR = 3;
export const MIN_DAGAR_PER_FONSTER = 2;

export type FonsterGranser = {
  maxDagar: number;
  maxInsatser: number;
  minDagar: number;
};

export const HELPERIOD_FONSTER: FonsterGranser = {
  maxDagar: HELPERIOD_MAX_DAGAR,
  maxInsatser: MOTOR_MAX_INSATSER,
  minDagar: MIN_DAGAR_PER_FONSTER,
};

export const SMALA_FONSTER: FonsterGranser = {
  maxDagar: SMALA_FONSTER_MAX_DAGAR,
  maxInsatser: SMALA_FONSTER_MAX_INSATSER,
  minDagar: MIN_DAGAR_PER_FONSTER,
};

/** @deprecated Använd SMALA_FONSTER.maxInsatser om du medvetet vill ha korta fönster. */
export const MAX_INSATSER_PER_FONSTER = HELPERIOD_FONSTER.maxInsatser;
/** @deprecated Använd SMALA_FONSTER.maxDagar om du medvetet vill ha korta fönster. */
export const MAX_DAGAR_PER_FONSTER = HELPERIOD_FONSTER.maxDagar;

type Insatspost = { date?: string | null; [f: string]: unknown };

export type Fonster = { from: string; to: string; dagar: number; insatser: number };

export function fonsterGranser(extra?: Partial<FonsterGranser>): FonsterGranser {
  return { ...HELPERIOD_FONSTER, ...extra };
}

function nastaDag(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function dagLista(from: string, to: string) {
  const ut: string[] = [];
  let d = from;
  let skydd = 0;
  while (d <= to && skydd++ < 400) {
    ut.push(d);
    d = nastaDag(d, 1);
  }
  return ut;
}

/** Bildar fönster. Default: ett fönster för perioder upp till 28 dagar inom motorns inputtak. */
export function delaPeriod(
  from: string,
  to: string,
  interventions: Insatspost[],
  granser: Partial<FonsterGranser> = {},
): Fonster[] {
  const g = fonsterGranser(granser);
  const perDag = new Map<string, number>();
  for (const i of interventions) {
    const d = String(i.date || "").slice(0, 10);
    if (d) perDag.set(d, (perDag.get(d) || 0) + 1);
  }
  const dagar = dagLista(from, to);
  const fonster: Fonster[] = [];
  let start = dagar[0] ?? from;
  let antal = 0;
  let langd = 0;
  for (const dag of dagar) {
    const n = perDag.get(dag) || 0;
    const overInsatser = langd > 0 && antal + n > g.maxInsatser;
    const overDagar = langd >= g.maxDagar;
    if (overInsatser || overDagar) {
      fonster.push({ from: start, to: nastaDag(dag, -1), dagar: langd, insatser: antal });
      start = dag;
      antal = 0;
      langd = 0;
    }
    antal += n;
    langd += 1;
  }
  if (langd > 0) fonster.push({ from: start, to: dagar[dagar.length - 1] ?? to, dagar: langd, insatser: antal });
  const sista = fonster[fonster.length - 1];
  const fore = fonster[fonster.length - 2];
  if (
    sista &&
    fore &&
    sista.dagar < g.minDagar &&
    fore.dagar + sista.dagar <= g.maxDagar &&
    fore.insatser + sista.insatser <= g.maxInsatser
  ) {
    fonster.splice(fonster.length - 2, 2, {
      from: fore.from,
      to: sista.to,
      dagar: fore.dagar + sista.dagar,
      insatser: fore.insatser + sista.insatser,
    });
  }
  return fonster;
}

/** Klipper en färdig payload till ett fönster och lägger föregående fönsters pass som låsta. */
export function payloadForFonster(
  payload: Record<string, unknown>,
  f: Fonster,
  lastaPass: Record<string, unknown>[],
): Record<string, unknown> {
  const wp = { ...(payload["workplace"] as Record<string, unknown>), start: f.from, end: f.to };
  const insatser = ((payload["interventions"] as Insatspost[]) || []).filter((i) => {
    const d = String(i.date || "").slice(0, 10);
    return !d || (d >= f.from && d <= f.to);
  });
  const franvaro = (payload["absences"] as Record<string, unknown>[]) || [];
  const bef = (payload["boundaryShifts"] as Record<string, unknown>[]) || [];
  const lasta = [...bef, ...lastaPass].filter((p) => {
    const d = String((p as { date?: string }).date || "").slice(0, 10);
    return !d || d < f.from || d > f.to || (p as { last?: boolean }).last === true;
  });
  const sedda = new Set<string>();
  const unika = lasta.filter((p) => {
    const nyckel = String((p as { id?: string }).id ?? "");
    if (sedda.has(nyckel)) return false;
    sedda.add(nyckel);
    return true;
  });
  const klippOpen = (key: "vacantShifts" | "openShifts") => {
    const rows = (payload[key] as { date?: string }[] | undefined) || [];
    return rows.filter((s) => {
      const d = String(s.date || "").slice(0, 10);
      return d >= f.from && d <= f.to;
    });
  };
  const vacantShifts = klippOpen("vacantShifts");
  return { ...payload, workplace: wp, interventions: insatser, absences: franvaro, boundaryShifts: unika, vacantShifts, openShifts: vacantShifts };
}

/** De sista dagarnas pass ur ett fönster – skickas som låsta pass i nästa fönster. */
export function svansPass(pass: Record<string, unknown>[], dagar = 27): Record<string, unknown>[] {
  const datum = [...new Set(pass.map((p) => String((p as { date?: string }).date || "")))].sort();
  const sista = new Set(datum.slice(-dagar));
  return pass.filter((p) => sista.has(String((p as { date?: string }).date || "")));
}
