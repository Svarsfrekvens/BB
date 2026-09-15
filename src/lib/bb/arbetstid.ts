/** Generell arbetstidsmodell. Avtalsmått är katalogdata, inte motorgrenar. */

export type WorkTimeModel = {
  id: string;
  name: string;
  weeklyMinutes: number;
  validFrom?: string;
  validTo?: string;
  /** Reserverat för T-04/T-05. Ingen automatisk reducering i motorn. */
  reductionRuleId?: string;
};

export type WorkTimeWindow = {
  start: string;
  end: string;
  modelId?: string;
  weeklyMinutes?: number;
};

export type WorkTimeWorkplace = {
  workTimeModels?: WorkTimeModel[];
  defaultWorkTimeModelId?: string;
};

export type WorkTimeEmployee = {
  ssg: number;
  ssgWindows?: { start: string; end: string; ssg: number }[];
  workTimeModelId?: string;
  workTimeWindows?: WorkTimeWindow[];
};

export const STANDARD_WORK_TIME_MODELS: WorkTimeModel[] = [
  { id: "helgfri-40", name: "Helgfri vecka 40 h", weeklyMinutes: 40 * 60 },
  { id: "vardag-helg-37", name: "Vardag och sön/helg 37 h", weeklyMinutes: 37 * 60 },
  { id: "standig-natt-36-20", name: "Ständig natt 36 h 20 min", weeklyMinutes: 36 * 60 + 20 },
];

export const DEFAULT_WORK_TIME_MODEL_ID = "vardag-helg-37";

export function defaultWeeklyHours(models: WorkTimeModel[] = STANDARD_WORK_TIME_MODELS, id = DEFAULT_WORK_TIME_MODEL_ID) {
  const m = models.find((x) => x.id === id);
  return (m?.weeklyMinutes ?? 37 * 60) / 60;
}

function modelCovers(model: WorkTimeModel | undefined, day: string) {
  if (!model) return false;
  if (model.validFrom && day < model.validFrom) return false;
  if (model.validTo && day > model.validTo) return false;
  return true;
}

export function ssgForDay(e: WorkTimeEmployee, day: string) {
  let ssg = e.ssg;
  for (const w of e.ssgWindows || []) {
    if (w.start <= day && day <= w.end) ssg = w.ssg;
  }
  return ssg;
}

/** Datumstyrd individuell modell → personmodell → verksamhetsdefault. */
export function giltigVerksamhetsDefault(workplace?: WorkTimeWorkplace) {
  const id = String(workplace?.defaultWorkTimeModelId || "").trim();
  if (!id) return undefined;
  return (workplace?.workTimeModels || []).some((m) => m.id === id) ? id : undefined;
}

export function harTillrackligArbetstidsmodell(
  e: { workTimeModelId?: string; workTimeWindows?: WorkTimeWindow[] },
  workplace?: WorkTimeWorkplace,
) {
  const fonster = e.workTimeWindows || [];
  if (fonster.some((w) => String(w.modelId || "").trim() || (w.weeklyMinutes != null && w.weeklyMinutes > 0))) return true;
  if (String(e.workTimeModelId || "").trim()) return true;
  return Boolean(giltigVerksamhetsDefault(workplace));
}

export function weeklyMinutesForDay(
  e: WorkTimeEmployee,
  day: string,
  rules: { fullTimeWeeklyHours: number },
  workplace?: WorkTimeWorkplace,
) {
  const models = new Map((workplace?.workTimeModels || []).map((m) => [m.id, m]));
  for (const w of e.workTimeWindows || []) {
    if (!(w.start <= day && day <= w.end)) continue;
    if (w.weeklyMinutes != null) return w.weeklyMinutes;
    const model = w.modelId ? models.get(w.modelId) : undefined;
    if (model && modelCovers(model, day)) return model.weeklyMinutes;
  }
  const person = e.workTimeModelId ? models.get(e.workTimeModelId) : undefined;
  if (person && modelCovers(person, day)) return person.weeklyMinutes;
  const fallbackId = workplace?.defaultWorkTimeModelId;
  const def = fallbackId ? models.get(fallbackId) : undefined;
  if (def && modelCovers(def, day)) return def.weeklyMinutes;
  return rules.fullTimeWeeklyHours * 60;
}

export function periodCapacityMinutes(
  e: WorkTimeEmployee,
  periodDays: string[],
  rules: { fullTimeWeeklyHours: number },
  workplace?: WorkTimeWorkplace,
) {
  return periodDays.reduce(
    (s, day) => s + (ssgForDay(e, day) / 100) * weeklyMinutesForDay(e, day, rules, workplace) / 7,
    0,
  );
}

export function listPeriodDays(from: string, to: string) {
  const out: string[] = [];
  const d = new Date(from + "T12:00:00Z");
  const end = new Date(to + "T12:00:00Z");
  while (d.getTime() <= end.getTime()) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}

export function modelIdMatchingMinutes(minutes: number, models: WorkTimeModel[] = STANDARD_WORK_TIME_MODELS) {
  const hit = models.find((m) => Math.abs(m.weeklyMinutes - minutes) < 0.5);
  return hit?.id ?? null;
}

/** Lägger till en katalograd för ett fritt veckomått. Ingen hårdkodad avtalsgren. */
export function ensureMinutesModel(minutes: number, models: WorkTimeModel[]) {
  const existing = modelIdMatchingMinutes(minutes, models);
  if (existing) return { models, id: existing };
  const id = `custom-${Math.round(minutes)}`;
  if (models.some((m) => m.id === id)) return { models, id };
  return {
    models: [...models, { id, name: `${(minutes / 60).toFixed(2)} h/vecka`, weeklyMinutes: minutes }],
    id,
  };
}
