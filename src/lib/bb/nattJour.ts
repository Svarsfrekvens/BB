/* ------------------------------------------------------------------ *
 * Vaken natt, sovande jour och nattlig närvaro är tre skilda krav.
 * Den här filen härleder bara jourkapacitet och jourgolv ur faktiskt
 * Före-schema. Den sätter aldrig nattbehörighet, yrkeskompetens eller
 * delegering.
 * ------------------------------------------------------------------ */

/** Andel nätter i perioden som måste ha Jo för att det ska räknas som
 *  verksamhetskrav på sovande jour (nattlig närvaro via jour, inte vaken natt). */
export const JOUR_NATTANDEL = 0.8;

export function isoDag(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function jourNamnFranSchema(pass?: { namn: string; jour?: boolean }[]) {
  return new Set((pass || []).filter((p) => p.jour).map((p) => p.namn));
}

/**
 * Härledd jourkapacitet från minst ett faktiskt Jo-pass i det importerade
 * schemat. Det är inte formell certifiering och får inte tolkas som vaken natt.
 * Explicit chefskomplettering (true/false) vinner över härledningen.
 */
export function harHärleddJour(
  explicit: boolean | null | undefined,
  namn: string,
  joNamn: Set<string>,
): boolean {
  if (explicit === true) return true;
  if (explicit === false) return false;
  return joNamn.has(namn);
}

export type JourMonster = {
  jourFloor: number;
  start: string;
  end: string;
  natter: number;
  medJo: number;
};

/**
 * Jourgolv ur Före-schemat. jourFloor = 1 när minst JOUR_NATTANDEL av
 * kalendernätterna i planperioden har minst ett Jo-pass med startdatum
 * den dagen. Tiderna tas från det vanligaste Jo-klockslaget, inte en påhittad mall.
 * Saknas Jo, eller är mönstret glesare, förblir jourFloor 0.
 */
export function jourMonsterFranSchema(
  pass: { datum: string; start: string; slut: string; jour?: boolean }[] | undefined,
  from: string,
  dagar: number,
): JourMonster {
  const natter = Math.max(0, Math.round(dagar || 0));
  const tom: JourMonster = { jourFloor: 0, start: "23:00", end: "06:30", natter, medJo: 0 };
  if (!from || natter < 1) return tom;
  const to = isoDag(from, natter - 1);
  const jo = (pass || []).filter((p) => p.jour && p.datum >= from && p.datum <= to);
  if (!jo.length) return { ...tom, natter };
  const medJo = new Set(jo.map((p) => p.datum)).size;
  const tider = new Map<string, number>();
  for (const p of jo) {
    const nyckel = `${p.start}-${p.slut}`;
    tider.set(nyckel, (tider.get(nyckel) || 0) + 1);
  }
  const topp = [...tider.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "23:00-06:30";
  const streck = topp.indexOf("-");
  const start = topp.slice(0, streck);
  const end = topp.slice(streck + 1);
  const andel = medJo / natter;
  const jourFloor = andel + 1e-12 >= JOUR_NATTANDEL ? 1 : 0;
  return { jourFloor, start, end, natter, medJo };
}

/** Chefens komplettering: jour och nattbehörighet är oberoende fält. */
export function kompletteraBehorighet(
  falt: string,
  varde: unknown,
  nu: Record<string, unknown>,
): Record<string, unknown> {
  const nasta = { ...nu, [falt]: varde };
  if (falt === "passprofil" && String(varde) === "natt") nasta.nattbehorig = true;
  return nasta;
}
