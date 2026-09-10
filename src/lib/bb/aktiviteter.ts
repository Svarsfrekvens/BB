/** Generell modell för planeringsaktiviteter. Ingen verksamhetsspecifik kod. */

export type AktivitetsKalla = "sekoia" | "schemaimport" | "manuellt" | "systemstandard";
export type AktivitetsEnhet = "minuter" | "timmar";
export type AktivitetsFrekvens =
  | "per_pass"
  | "per_kund_vecka"
  | "per_kund_manad"
  | "per_vecka"
  | "per_manad"
  | "per_period"
  | "specifikt_datum";

export type PlanAktivitet = {
  id: string;
  aktivitetstyp: string;
  namn: string;
  kategori: "kundnara" | "verksamhet";
  kundnara: boolean;
  kalla: AktivitetsKalla;
  omfattning: number;
  enhet: AktivitetsEnhet;
  frekvens: AktivitetsFrekvens;
  kundId?: string;
  medarbetareId?: string;
  from?: string;
  till?: string;
  datum?: string;
  start?: string;
  aktiv: boolean;
  verksamhetsId?: string;
  prioritet?: number;
  styrka?: "maste" | "onskemal";
};

export type ExpanderadAktivitet = {
  typ: string;
  namn: string;
  kundnara: boolean;
  timmar: number;
  kund?: string;
  medarbetare?: string;
  kalla: AktivitetsKalla;
};

export const STANDARD_AKTIVITETER: Omit<PlanAktivitet, "verksamhetsId">[] = [
  { id: "lasa_journal", aktivitetstyp: "lasa_journal", namn: "Läsa journal vid passstart", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 10, enhet: "minuter", frekvens: "per_pass", aktiv: false, styrka: "onskemal" },
  { id: "skriva_journal", aktivitetstyp: "skriva_journal", namn: "Skriva journal vid passlut", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 15, enhet: "minuter", frekvens: "per_pass", aktiv: false, styrka: "onskemal" },
  { id: "kontaktpersonstid", aktivitetstyp: "kontaktpersonstid", namn: "Kontaktpersonstid", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 30, enhet: "minuter", frekvens: "per_kund_vecka", aktiv: false, styrka: "onskemal" },
  { id: "veckoavstamning", aktivitetstyp: "veckoavstamning", namn: "Veckoavstämning kund", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 1, enhet: "timmar", frekvens: "per_kund_vecka", aktiv: false, styrka: "onskemal" },
  { id: "manadsuppfoljning", aktivitetstyp: "manadsuppfoljning", namn: "Månadsuppföljning kund", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 1, enhet: "timmar", frekvens: "per_kund_manad", aktiv: false, styrka: "onskemal" },
  { id: "gp", aktivitetstyp: "gp", namn: "Genomförandeplan", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 1, enhet: "timmar", frekvens: "per_kund_manad", aktiv: false, styrka: "onskemal" },
  { id: "sip", aktivitetstyp: "sip", namn: "SIP", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 2, enhet: "timmar", frekvens: "per_kund_manad", aktiv: false, styrka: "onskemal" },
  { id: "husmote", aktivitetstyp: "husmote", namn: "Husmöte", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 1, enhet: "timmar", frekvens: "per_manad", aktiv: false, styrka: "onskemal" },
  { id: "samverkan_kund", aktivitetstyp: "samverkan_kund", namn: "Samverkan kring kund", kategori: "kundnara", kundnara: true, kalla: "systemstandard", omfattning: 30, enhet: "minuter", frekvens: "per_kund_vecka", aktiv: false, styrka: "onskemal" },
  { id: "verksamhetsmote", aktivitetstyp: "verksamhetsmote", namn: "Verksamhetsmöte", kategori: "verksamhet", kundnara: false, kalla: "systemstandard", omfattning: 2, enhet: "timmar", frekvens: "per_manad", aktiv: false, styrka: "onskemal" },
  { id: "kvalitetsrad", aktivitetstyp: "kvalitetsrad", namn: "Regionalt kvalitetsråd", kategori: "verksamhet", kundnara: false, kalla: "systemstandard", omfattning: 2, enhet: "timmar", frekvens: "per_manad", aktiv: false, styrka: "onskemal" },
  { id: "handledning", aktivitetstyp: "handledning", namn: "Handledning", kategori: "verksamhet", kundnara: false, kalla: "systemstandard", omfattning: 2, enhet: "timmar", frekvens: "per_manad", aktiv: false, styrka: "onskemal" },
];

const FORBJUDNA = /^(apt|arbetsplatsträff|kundmöte|individuell aktivitet)/i;

export function standardKatalog(): PlanAktivitet[] {
  return STANDARD_AKTIVITETER.filter((a) => !FORBJUDNA.test(a.namn)).map((a) => ({ ...a }));
}

function tillTimmar(omfattning: number, enhet: AktivitetsEnhet) {
  return enhet === "timmar" ? omfattning : omfattning / 60;
}

export function veckorIPeriod(fran: string, till: string) {
  const ms = Date.parse(till + "T12:00:00Z") - Date.parse(fran + "T12:00:00Z");
  return Math.max(1, Math.round(ms / 86400000 + 1) / 7);
}

export function manaderIPeriod(fran: string, till: string) {
  const a = new Date(fran + "T12:00:00Z");
  const b = new Date(till + "T12:00:00Z");
  return Math.max(1, (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + (b.getUTCMonth() - a.getUTCMonth()) + 1);
}

export function sekoiaOverlappar(rader: { insats?: string }[], typ: string) {
  const namn = STANDARD_AKTIVITETER.find((a) => a.aktivitetstyp === typ)?.namn || typ;
  const nyckel = namn.toLowerCase().slice(0, 12);
  return rader.some((r) => String(r.insats || "").toLowerCase().includes(nyckel));
}

export function expanderaAktiviteter(opts: {
  aktiviteter: PlanAktivitet[];
  fran: string;
  till: string;
  arbetspass: number;
  kunder: string[];
  kontaktpersoner: Record<string, string>;
  sekoiaRader?: { insats?: string; kund?: string }[];
}): ExpanderadAktivitet[] {
  const veckor = veckorIPeriod(opts.fran, opts.till);
  const manader = manaderIPeriod(opts.fran, opts.till);
  const ut: ExpanderadAktivitet[] = [];
  for (const a of opts.aktiviteter) {
    if (!a.aktiv) continue;
    if (FORBJUDNA.test(a.namn)) continue;
    if (a.kalla !== "sekoia" && sekoiaOverlappar(opts.sekoiaRader || [], a.aktivitetstyp)) continue;
    const tim = tillTimmar(a.omfattning, a.enhet);
    const kunder = a.kundId ? [a.kundId] : opts.kunder;
    if (a.frekvens === "per_pass") {
      ut.push({ typ: a.aktivitetstyp, namn: a.namn, kundnara: a.kundnara, timmar: tim * opts.arbetspass, kalla: a.kalla });
      continue;
    }
    if (a.frekvens === "per_kund_vecka") {
      for (const kund of kunder) {
        ut.push({
          typ: a.aktivitetstyp,
          namn: a.namn,
          kundnara: a.kundnara,
          timmar: tim * veckor,
          kund,
          ...(opts.kontaktpersoner[kund] ? { medarbetare: opts.kontaktpersoner[kund] } : {}),
          kalla: a.kalla,
        });
      }
      continue;
    }
    if (a.frekvens === "per_kund_manad") {
      for (const kund of kunder) {
        ut.push({
          typ: a.aktivitetstyp,
          namn: a.namn,
          kundnara: a.kundnara,
          timmar: tim * manader,
          kund,
          ...(opts.kontaktpersoner[kund] ? { medarbetare: opts.kontaktpersoner[kund] } : {}),
          kalla: a.kalla,
        });
      }
      continue;
    }
    const ganger = a.frekvens === "per_vecka" ? veckor : a.frekvens === "per_manad" ? manader : 1;
    ut.push({
      typ: a.aktivitetstyp,
      namn: a.namn,
      kundnara: a.kundnara,
      timmar: tim * ganger,
      ...(a.kundId ? { kund: a.kundId } : {}),
      ...(a.medarbetareId ? { medarbetare: a.medarbetareId } : {}),
      kalla: a.kalla,
    });
  }
  return ut;
}

export function aktivitetstimmar(expanderade: ExpanderadAktivitet[]) {
  return {
    kundnaraH: expanderade.filter((a) => a.kundnara).reduce((s, a) => s + a.timmar, 0),
    ejKundnaraH: expanderade.filter((a) => !a.kundnara).reduce((s, a) => s + a.timmar, 0),
  };
}

export function kunderUtanKontakt(kunder: string[], kontakt: Record<string, string>, aktiviteter: PlanAktivitet[]) {
  const behovs = aktiviteter.some(
    (a) =>
      a.aktiv &&
      ["kontaktpersonstid", "veckoavstamning", "manadsuppfoljning", "gp"].includes(a.aktivitetstyp),
  );
  if (!behovs) return [];
  return kunder.filter((k) => !kontakt[k]);
}
