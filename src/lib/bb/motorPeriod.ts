/* ------------------------------------------------------------------ *
 * Delar en lång period i körningsfönster som optimeringsmotorn klarar.
 * Ingen beräkning av behov sker här – bara uppdelning av redan byggd
 * data i datumordning.
 * ------------------------------------------------------------------ */

export const MAX_INSATSER_PER_FONSTER = 320;
export const MAX_DAGAR_PER_FONSTER = 3;
export const MIN_DAGAR_PER_FONSTER = 2;

type Insatspost = { date?: string | null; [f: string]: unknown };

export type Fonster = { from: string; to: string; dagar: number; insatser: number };

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

/** Bildar små fönster som hinner beräknas innan serveranropets tidsgräns. */
export function delaPeriod(from: string, to: string, interventions: Insatspost[]): Fonster[] {
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
    const overInsatser = langd > 0 && antal + n > MAX_INSATSER_PER_FONSTER;
    const overDagar = langd >= MAX_DAGAR_PER_FONSTER;
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
  // Ett mycket kort sistafönster går sällan att lösa: personalens
  // sysselsättningsgrad räknas om per fönster och rymmer då inte ett helt pass.
  // Slå därför samman svansen med föregående fönster när det går.
  const sista = fonster[fonster.length - 1];
  const fore = fonster[fonster.length - 2];
  if (
    sista &&
    fore &&
    sista.dagar < MIN_DAGAR_PER_FONSTER &&
    fore.dagar + sista.dagar <= MAX_DAGAR_PER_FONSTER &&
    fore.insatser + sista.insatser <= MAX_INSATSER_PER_FONSTER
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
  return { ...payload, workplace: wp, interventions: insatser, absences: franvaro, boundaryShifts: unika };
}

/** De sista dagarnas pass ur ett fönster – skickas som låsta pass i nästa fönster. */
export function svansPass(pass: Record<string, unknown>[], dagar = 2): Record<string, unknown>[] {
  const datum = [...new Set(pass.map((p) => String((p as { date?: string }).date || "")))].sort();
  const sista = new Set(datum.slice(-dagar));
  return pass.filter((p) => sista.has(String((p as { date?: string }).date || "")));
}
