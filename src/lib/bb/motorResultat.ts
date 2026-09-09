/* ------------------------------------------------------------------ *
 * Översätter optimeringsmotorns svar till appens format: pass i samma
 * form som Medvind-passen och flyttade insatser i samma form som den
 * lokala beräkningen ger. Inga nya beräkningar av kundbehov sker här.
 * ------------------------------------------------------------------ */

/** Svenska rubriker för motorns regelkoder. */
export const REGEL_RUBRIK: Record<string, string> = {
  REST: "Dygnsvila",
  SHIFT_OVERLAP: "Pass krockar",
  CONTRACT: "Sysselsättningsgrad",
  WEEK_HOURS: "Veckoarbetstid",
  CONSECUTIVE: "Arbetsdagar i följd",
  NIGHT: "Nattbehörighet",
  SKILL: "Kompetens på pass",
  SHIFT_LENGTH: "Passlängd",
  ABSENCE: "Frånvaro",
  STATUS: "Anställningsstatus",
  COVERAGE: "Täckning av insats",
  UNCOVERED: "Obemannat behov",
  SIMULTANEOUS: "Dubbelbemanning",
  WINDOW: "Insatsens tidsfönster",
  TASK_SKILL: "Kompetens på insats",
  ON_DUTY: "Insats utanför pass",
  TASK_OVERLAP: "Insatser krockar",
  NIGHT_FLOOR: "Vaken natt – grundbemanning",
  DUPLICATE_SHIFT: "Dubblerat pass",
  UNKNOWN_TASK: "Okänd insats",
  TIME: "Tidsangivelse",
  STRUCTURE: "Underlagets struktur",
  INPUT: "Underlaget",
};

export type MotorPass = {
  id: string;
  namn: string;
  datum: string;
  start: string;
  slut: string;
  timmar: number;
  jour: boolean;
  natt: boolean;
  vikarie: boolean;
  typ: string;
  last: boolean;
};

export type MotorFlytt = { id: string; fran: string; till: string };

export type MotorTilldelning = {
  insatsId: string;
  datum: string;
  medarbetare: string;
  start: string;
  slut: string;
};

export type MotorObemannad = { insats: string; datum: string; minuter: number; antal: number };

export type MotorSchema = {
  solverStatus: string;
  explanation: string;
  pass: MotorPass[];
  tilldelningar: MotorTilldelning[];
  flyttade: MotorFlytt[];
  obemannade: MotorObemannad[];
  objective: number | null;
  bound: number | null;
  objectiveBreakdown: { costOre: number; continuityOre: number; spreadOre: number } | null;
};

type Rast = { offset?: number; minutes?: number };

function minuter(t: string) {
  const d = String(t || "").split(":");
  return (Number(d[0]) || 0) * 60 + (Number(d[1]) || 0);
}

function klocka(min: number) {
  const v = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
}

/** Betald tid i timmar: passets längd minus raster, över midnatt hanterat. */
export function betaldTid(start: string, slut: string, raster: Rast[] = []) {
  const a = minuter(start);
  let b = minuter(slut);
  if (b <= a) b += 1440;
  const rast = (raster || []).reduce((s, r) => s + (Number(r.minutes) || 0), 0);
  return Math.max(0, b - a - rast) / 60;
}

/** UTC-minuter sedan epok → klockslag i svensk tid. */
export function stockholmKlocka(utcMinuter: number) {
  const d = new Date(Number(utcMinuter) * 60000);
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Stockholm",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export type Uppslag = {
  /** motorns employeeId → medarbetare i appen */
  medarbetare: Record<string, { namn: string; vikarie: boolean }>;
  /** motorns interventionId → appens insatsrad */
  insatser: Record<string, { radId: string; kund: string; insats: string; start: string }>;
};

/** Tolkar motorns schema (JSON-strängen ur serverfunktionen). */
export function tolkaMotorSchema(schemaJson: string, upp: Uppslag): MotorSchema | null {
  let schema: any = null;
  try {
    schema = JSON.parse(schemaJson);
  } catch {
    return null;
  }
  if (!schema) return null;

  const pass: MotorPass[] = ((schema.shifts as any[]) || []).map((s, i) => {
    const person = upp.medarbetare[String(s.employeeId)] || { namn: String(s.employeeId), vikarie: false };
    const start = String(s.start || "00:00");
    const slut = String(s.end || "00:00");
    return {
      id: String(s.id || `motor-${i}`),
      namn: person.namn,
      datum: String(s.date || "").slice(0, 10),
      start,
      slut,
      timmar: betaldTid(start, slut, (s.breaks as Rast[]) || []),
      jour: false,
      natt: minuter(start) >= 22 * 60 || minuter(slut) <= minuter(start),
      vikarie: Boolean(person.vikarie),
      typ: String(s.type || "day"),
      last: false,
    };
  });

  const tilldelningar: MotorTilldelning[] = [];
  const flyttade: MotorFlytt[] = [];
  for (const a of (schema.assignments as any[]) || []) {
    const nyckel = String(a.occurrenceId || "");
    const bit = nyckel.split("@");
    const insatsId = bit[0] ?? "";
    const datum = (bit[1] ?? "").slice(0, 10);
    const person = upp.medarbetare[String(a.employeeId)];
    const start = stockholmKlocka(Number(a.start));
    const slut = stockholmKlocka(Number(a.end));
    tilldelningar.push({ insatsId, datum, medarbetare: person?.namn ?? String(a.employeeId), start, slut });
    const rad = upp.insatser[insatsId];
    if (rad && rad.start && rad.start !== start) flyttade.push({ id: rad.radId, fran: rad.start, till: start });
  }

  const obemannade: MotorObemannad[] = ((schema.uncovered as any[]) || []).map((u) => ({
    insats: String(u?.name ?? "Insats"),
    datum: String(u?.date ?? "").slice(0, 10),
    minuter: Number(u?.minutes) || 0,
    antal: Number(u?.count) || 0,
  }));

  return {
    solverStatus: String(schema.solverStatus || "UNKNOWN"),
    explanation: String(schema.explanation || ""),
    pass,
    tilldelningar,
    flyttade,
    obemannade,
    objective: schema.objective ?? null,
    bound: schema.bound ?? null,
    objectiveBreakdown: schema.objectiveBreakdown
      ? {
          costOre: Number(schema.objectiveBreakdown.costOre) || 0,
          continuityOre: Number(schema.objectiveBreakdown.continuityOre) || 0,
          spreadOre: Number(schema.objectiveBreakdown.spreadOre) || 0,
        }
      : null,
  };
}

/** Slår ihop resultatet från flera körningsfönster till ett. */
export function slaSamman(delar: MotorSchema[]): MotorSchema | null {
  if (!delar.length) return null;
  const forsta = delar[0]!;
  return {
    solverStatus: delar.every((d) => d.solverStatus === "OPTIMAL") ? "OPTIMAL" : "FEASIBLE",
    explanation: forsta.explanation,
    pass: delar.flatMap((d) => d.pass),
    tilldelningar: delar.flatMap((d) => d.tilldelningar),
    flyttade: delar.flatMap((d) => d.flyttade),
    obemannade: delar.flatMap((d) => d.obemannade),
    objective: delar.reduce((s, d) => s + (Number(d.objective) || 0), 0),
    bound: delar.reduce((s, d) => s + (Number(d.bound) || 0), 0),
    objectiveBreakdown: delar.some((d) => d.objectiveBreakdown)
      ? {
          costOre: delar.reduce((s, d) => s + (d.objectiveBreakdown?.costOre || 0), 0),
          continuityOre: delar.reduce((s, d) => s + (d.objectiveBreakdown?.continuityOre || 0), 0),
          spreadOre: delar.reduce((s, d) => s + (d.objectiveBreakdown?.spreadOre || 0), 0),
        }
      : null,
  };
}

/** Passändringar i text: jämför motorns pass med det inlästa schemat. */
export function passForandringar(fore: { namn: string; datum: string; start: string; slut: string }[], efter: MotorPass[]) {
  const nyckel = (p: { namn: string; datum: string; start: string; slut: string }) => `${p.namn}|${p.datum}|${p.start}|${p.slut}`;
  const foreSet = new Set(fore.map(nyckel));
  const efterSet = new Set(efter.map(nyckel));
  const ut: { typ: string; text: string }[] = [];
  for (const p of efter) {
    if (!foreSet.has(nyckel(p))) ut.push({ typ: "nytt", text: `${p.namn} ${p.datum} ${p.start}–${p.slut}${p.vikarie ? " (vikarie)" : ""}` });
  }
  for (const p of fore) {
    if (!efterSet.has(nyckel(p))) ut.push({ typ: "borttaget", text: `${p.namn} ${p.datum} ${p.start}–${p.slut} ligger inte i förslaget` });
  }
  return ut;
}

/** Klockslag för visning (exporteras för vyerna). */
export const motorKlocka = klocka;
