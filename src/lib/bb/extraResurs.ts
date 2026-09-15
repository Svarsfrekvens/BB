/** Explicit extra resurs som VC registrerar. Aldrig auto-skapad, inga dolda default. */

export const EXTRA_RESURS_SLAG = ["vikarie", "extern", "tillfallig"] as const;
export type ExtraResursSlag = (typeof EXTRA_RESURS_SLAG)[number];

export type ExtraResurs = {
  id: string;
  namn: string;
  slag: ExtraResursSlag;
  tillgangligaDatum: string[];
  tidigastStart: string;
  senastSlut: string;
  jour: boolean;
  nattbehorig: boolean;
  kompetenser: string[];
  delegering: boolean;
  helg: boolean;
  timkostnad: number | null;
  maxTimmar: number | null;
};

const ISO = /^\d{4}-\d{2}-\d{2}$/;
const KLOCKA = /^([01]\d|2[0-3]):[0-5]\d$/;

export function nyExtraResursId() {
  return "x" + Math.random().toString(36).slice(2, 10);
}

/** Tom blankett. Inga kompetenser, ingen jour/natt/helg/delegering, ingen SSG. */
export function tomExtraResurs(): ExtraResurs {
  return {
    id: nyExtraResursId(),
    namn: "",
    slag: "extern",
    tillgangligaDatum: [],
    tidigastStart: "",
    senastSlut: "",
    jour: false,
    nattbehorig: false,
    kompetenser: [],
    delegering: false,
    helg: false,
    timkostnad: null,
    maxTimmar: null,
  };
}

export function tolkaDatumlista(text: string): string[] {
  const seen = new Set<string>();
  const ut: string[] = [];
  for (const raw of String(text || "").split(/[\s,;]+/)) {
    const d = raw.trim();
    if (!ISO.test(d) || seen.has(d)) continue;
    seen.add(d);
    ut.push(d);
  }
  return ut;
}

export function arHelgdatum(iso: string) {
  const wd = new Date(`${iso}T12:00:00Z`).getUTCDay();
  return wd === 0 || wd === 6;
}

export function valideraExtraResurs(r: ExtraResurs, upptagnaNamn: string[] = []) {
  const fel: string[] = [];
  const namn = String(r.namn || "").trim();
  if (!namn) fel.push("Ange namn eller benämning.");
  if (namn && upptagnaNamn.some((n) => n.toLowerCase() === namn.toLowerCase())) {
    fel.push("Namnet finns redan bland registrerade resurser.");
  }
  if (!EXTRA_RESURS_SLAG.includes(r.slag)) fel.push("Välj resurstyp.");
  if (r.tidigastStart && !KLOCKA.test(r.tidigastStart)) fel.push("Tillgänglig från-tid är ogiltig.");
  if (r.senastSlut && !KLOCKA.test(r.senastSlut)) fel.push("Tillgänglig till-tid är ogiltig.");
  const kostnad = Number(r.timkostnad);
  if (!(Number.isFinite(kostnad) && kostnad > 0)) fel.push("Ange timkostnad större än 0 kr.");
  if (r.maxTimmar != null && r.maxTimmar !== undefined) {
    const max = Number(r.maxTimmar);
    if (!Number.isFinite(max) || max < 0) fel.push("Max arbetstid måste vara ett tal ≥ 0.");
  }
  return { ok: fel.length === 0, fel };
}

export function extraTillMedarbetare(r: ExtraResurs) {
  const namn = String(r.namn || "").trim();
  const datum = (r.tillgangligaDatum || []).filter((d) => ISO.test(d));
  const datumEfterHelg = r.helg ? datum : datum.filter((d) => !arHelgdatum(d));
  const baraJour = r.jour === true && r.nattbehorig !== true && !r.tidigastStart && !r.senastSlut;
  return {
    namn,
    vakant: false,
    vikarie: r.slag === "vikarie",
    grad: 0,
    samordnare: false,
    delegering: r.delegering === true,
    jour: r.jour === true,
    nattbehorig: r.nattbehorig === true,
    passprofil: baraJour ? "jour" : "",
    helg: r.helg ? "alla" : "inga",
    tidigastStart: r.tidigastStart || "",
    senastSlut: r.senastSlut || "",
    maxDagarIFoljd: 0,
    franvaro: "ingen",
    timkostnad: Number(r.timkostnad) > 0 ? Number(r.timkostnad) : 0,
    anstallning: "timme",
    resourceType: "temporary" as const,
    extraSlag: r.slag,
    tillgangligaDatum: datumEfterHelg,
    kompetenser: (r.kompetenser || []).map((k) => String(k).trim()).filter(Boolean),
    maxTimmar: r.maxTimmar != null && Number(r.maxTimmar) >= 0 ? Number(r.maxTimmar) : null,
    villkor: [] as { id: string; typ: string; styrka: string; aktiv: boolean }[],
  };
}
