/** Startar bemanningsberäkning från Hem/processrad/felsökningsvy. Ingen ny motorlogik. */

import {
  DEFAULT_WORK_TIME_MODEL_ID,
  STANDARD_WORK_TIME_MODELS,
  listPeriodDays,
  periodCapacityMinutes,
} from "./arbetstid";
import { delaPeriod, payloadForFonster, svansPass } from "./motorPeriod";
import { passForandringar, slaSamman, tolkaMotorSchema, type MotorSchema } from "./motorResultat";
import { motorStatus, optimeraMedMotor, type MotorSvar } from "./motor.functions";
import { byggMotorPayload, type PayloadResultat } from "./motorPayload";
import { readinessFranApi } from "./vcFlode";
import type { VyApi, VyTillstand } from "./vy";

export function byggUnderlagForBerakning(api: VyApi, state: VyTillstand | Record<string, unknown> | null) {
  const period = (state?.period ?? null) as { from?: string } | null;
  const rader = api.arbetsRader();
  const personal = api.harPersonal() ? api.personalRader() : [];
  const heltidPerNamn: Record<string, number> = {};
  for (const r of personal) {
    const namn = String(r["Medarbetare"] ?? "").trim();
    const h = Number(r["Heltid h/vecka"]);
    if (namn && Number.isFinite(h) && h > 0) heltidPerNamn[namn] = h;
  }
  return byggMotorPayload({
    rader,
    medarbetare: api.medarbetare(),
    from: String(period?.from || rader[0]?.datum || "").slice(0, 10),
    dagar: api.planDays(),
    timkostnad: Number((state as { hourlyCost?: number } | null)?.hourlyCost) || 270,
    heltidPerNamn,
    regler: api.motorRegler(),
    schemaPass: api.schemaPassHorisont(),
    planAktiviteter: api.planAktiviteter(),
    kontaktpersoner: api.kontaktpersoner(),
    objectiveWeights: {
      continuitySek: Number((state as Record<string, unknown> | null)?.["continuitySek"] ?? 50),
      spreadSekPerPermille: Number((state as Record<string, unknown> | null)?.["spreadSekPerPermille"] ?? 2.5),
      uncoveredSekPerMinute: Number((state as Record<string, unknown> | null)?.["uncoveredSekPerMinute"] ?? 500),
    },
  });
}

export type KorUtfall = "motor" | "lokal" | "blockerad";

export async function korBemanningsbalans(opts: {
  api: VyApi;
  state: VyTillstand | Record<string, unknown> | null;
  sekunder?: number;
  onSteg?: (s: string) => void;
}): Promise<KorUtfall> {
  const r = readinessFranApi(opts.api);
  if (!r.ready) return "blockerad";

  const tid = opts.sekunder ?? 45;
  const steg = (s: string) => opts.onSteg?.(s);

  let tillganglig = false;
  try {
    const status = await motorStatus();
    tillganglig = Boolean(status?.installd && status?.klar);
  } catch {
    tillganglig = false;
  }
  if (!tillganglig) {
    opts.api.skapa();
    return "lokal";
  }

  const underlagMotor = byggUnderlagForBerakning(opts.api, opts.state);
  const insatser = (underlagMotor.payload["interventions"] as { date?: string }[]) || [];
  const fonster = delaPeriod(underlagMotor.info.from, underlagMotor.info.to, insatser);
  const delar: MotorSchema[] = [];
  let lasta: Record<string, unknown>[] = [];
  let senasteSummary: Record<string, unknown> | null = null;

  const lokal = () => {
    opts.api.skapa();
    return "lokal" as const;
  };

  try {
    for (let i = 0; i < fonster.length; i++) {
      const f = fonster[i]!;
      steg(`Fönster ${i + 1} av ${fonster.length}: ${f.from} – ${f.to}`);
      const del = payloadForFonster(underlagMotor.payload, f, lasta);
      let svar: MotorSvar | null = null;
      for (let forsok = 0; forsok < 6; forsok++) {
        svar = await optimeraMedMotor({ data: { data: del, seconds: tid } });
        if (svar.ok || svar.status !== "429") break;
        steg(`En beräkning pågår redan – försöker igen (${forsok + 1}/6)…`);
        await new Promise((res) => setTimeout(res, 5000));
      }
      if (!svar || !svar.ok) return lokal();
      const schema = svar.schemaJson
        ? tolkaMotorSchema(svar.schemaJson, { medarbetare: underlagMotor.medarbetarKarta, insatser: underlagMotor.insatsKarta })
        : null;
      if (svar.summary) senasteSummary = svar.summary;
      if (!schema || !schema.pass.length || svar.status === "INFEASIBLE" || svar.status === "UNKNOWN" || svar.status === "MODEL_INVALID") {
        return lokal();
      }
      delar.push(schema);
      const rapass = (JSON.parse(svar.schemaJson || "{}").shifts as Record<string, unknown>[]) || [];
      lasta = svansPass(rapass, 27).map((p) => ({ ...p, last: true }));
    }

    const samlat = slaSamman(delar);
    if (!samlat) return lokal();
    const original = opts.api.schemaPassOriginal();
    const forandringar = passForandringar(original, samlat.pass);
    const obemannadeTimmar = samlat.obemannade.reduce((s, u) => s + (u.minuter * u.antal) / 60, 0);
    const extraVarningar = obemannadeTimmar
      ? [
          `${samlat.obemannade.length} insatstillfällen (${obemannadeTimmar.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} timmar) kunde inte bemannas utan att bryta mot vila-, helg- eller jourreglerna.`,
        ]
      : [];
    const infordes = opts.api.anvandMotorResultat({
      pass: samlat.pass,
      flyttade: samlat.flyttade,
      forandringar,
      varningar: [...underlagMotor.varningar, ...extraVarningar],
      solverStatus: samlat.solverStatus,
      explanation: samlat.explanation,
      tilldelningar: samlat.tilldelningar,
      fonster: fonster.length,
      objectiveBreakdown: samlat.objectiveBreakdown,
      summary: senasteSummary,
    });
    return infordes ? "motor" : lokal();
  } catch {
    return lokal();
  }
}

export function kanStartaFranEttKlick(api: VyApi) {
  return readinessFranApi(api).ready;
}

/** Diagnos för felsökningsvyn – visas inte i huvudflödet. */
export function byggDiagnos(p: PayloadResultat) {
  const ut: string[] = [];
  const anstallda = (p.payload["employees"] as { status: string; skills: string[]; night: boolean; ssg: number }[]) || [];
  const aktiva = anstallda.filter((e) => e.status === "active");
  const insatser = (p.payload["interventions"] as { skills: string[]; minutes: number }[]) || [];
  const utanKompetens = insatser.filter((i) => i.skills.length && !aktiva.some((e) => i.skills.every((s) => e.skills.includes(s))));
  if (utanKompetens.length) ut.push(`${utanKompetens.length} insatser kräver en kompetens som ingen tillgänglig medarbetare har.`);
  const nattgolv = p.info.regler.nightFloor;
  const nattpersonal = aktiva.filter((e) => e.night).length;
  if (nattgolv > nattpersonal) ut.push(`Vaken natt kräver ${nattgolv} medarbetare men bara ${nattpersonal} har nattbehörighet.`);
  const jourgolv = p.info.regler.jourFloor;
  const jourpersonal = aktiva.filter((e) => Boolean((e as { jour?: boolean }).jour)).length;
  if (jourgolv > jourpersonal) ut.push(`Sovande jour kräver ${jourgolv} medarbetare men bara ${jourpersonal} har jourbehörighet.`);
  const wp = p.payload["workplace"] as { workTimeModels?: { id: string; weeklyMinutes: number }[]; defaultWorkTimeModelId?: string };
  const rules = p.payload["rules"] as { fullTimeWeeklyHours: number };
  const days = listPeriodDays(String(p.info.from), String(p.info.to));
  const tak = aktiva.reduce(
    (s, e) =>
      s +
      periodCapacityMinutes(e as { ssg: number }, days, rules, {
        workTimeModels: wp?.workTimeModels?.length ? wp.workTimeModels : STANDARD_WORK_TIME_MODELS,
        defaultWorkTimeModelId: wp?.defaultWorkTimeModelId || DEFAULT_WORK_TIME_MODEL_ID,
      }) /
        60,
    0,
  );
  const behov = insatser.reduce((s, i) => s + i.minutes, 0) / 60;
  if (tak < behov) ut.push(`Personalens sysselsättningsgrader ger högst ${tak.toFixed(0)} timmar i perioden, men insatserna kräver minst ${behov.toFixed(0)} timmar.`);
  if (!ut.length) ut.push("Underlaget ser rimligt ut på ytan – titta på tidsfönster, frånvaro och passmallar.");
  return ut;
}
