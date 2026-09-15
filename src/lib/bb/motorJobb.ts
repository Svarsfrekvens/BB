/** Klient för asynkron motor-jobb. Ingen ny solverlogik. */

import { hamtaMotorJobb, startaMotorJobb, type MotorJobbSvar } from "./motor.functions";
import type { VyApi } from "./vy";

export type SparatMotorJobb = {
  id: string;
  inputHash: string;
  underlagHash: string;
  started: string;
  phase?: string;
  phaseText?: string;
  outcome?: string | null;
  stale?: boolean;
};

let pollTimer: ReturnType<typeof setInterval> | null = null;
let pollApi: VyApi | null = null;
let onKlart: ((svar: MotorJobbSvar, job: SparatMotorJobb) => void) | null = null;

const FASER = ["preparing", "checking", "solving", "validating", "completed"] as const;

export function balansUtfallText(outcome: string | null | undefined) {
  if (outcome === "balans_klar") return "Balans klar";
  if (outcome === "basta_hittade") return "Bästa hittade Balans";
  if (outcome === "kompletteras") return "Balans behöver kompletteras";
  if (outcome === "tekniskt_fel") return "Kunde inte skapa Balans";
  return "";
}

export function fasSteg(phase: string | undefined) {
  const nu = String(phase || "queued");
  const idx = FASER.indexOf(nu as (typeof FASER)[number]);
  return [
    { id: "preparing", label: "Underlag kontrollerat", klar: idx > 0 || nu === "completed" },
    { id: "checking", label: "Styrande villkor kontrollerade", klar: idx > 1 || nu === "completed" },
    { id: "solving", label: "Söker bästa möjliga bemanning", klar: idx > 2 || nu === "completed", pa: nu === "solving" },
    { id: "validating", label: "Kontrollerar resultat", klar: nu === "completed", pa: nu === "validating" },
  ];
}

export function stoppaMotorJobbPoll() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  pollApi = null;
}

export async function startaAsynkBalans(opts: {
  api: VyApi;
  del: unknown;
  underlagHash: string;
  sekunder: number;
  onKlart: (svar: MotorJobbSvar, job: SparatMotorJobb) => void;
}) {
  onKlart = opts.onKlart;
  const svar = await startaMotorJobb({ data: { data: opts.del, seconds: opts.sekunder } });
  if (!svar.ok || !svar.jobId) return svar;
  opts.api.sattMotorJobb?.({
    id: svar.jobId,
    inputHash: String(svar.inputHash || ""),
    underlagHash: opts.underlagHash,
    started: new Date().toISOString(),
    phase: svar.phase,
    phaseText: svar.phaseText,
    outcome: svar.outcome,
    stale: false,
  });
  startaMotorJobbPoll(opts.api, opts.onKlart);
  return svar;
}

export function startaMotorJobbPoll(api: VyApi, klart: (svar: MotorJobbSvar, job: SparatMotorJobb) => void) {
  pollApi = api;
  onKlart = klart;
  if (pollTimer) return;
  void tick();
  pollTimer = setInterval(() => void tick(), 2000);
}

async function tick() {
  const api = pollApi;
  if (!api) return;
  const job = api.motorJobb?.();
  if (!job?.id) {
    stoppaMotorJobbPoll();
    return;
  }
  const svar = await hamtaMotorJobb({ data: { jobId: job.id } });
  const nuHash = api.underlagFingeravtryck?.() || job.underlagHash;
  const stale = nuHash !== job.underlagHash;
  if (!svar.ok) {
    api.sattMotorJobb?.({
      ...job,
      stale,
      phaseText: "Kontakten avbröts – kontrollerar om beräkningen fortfarande pågår",
    });
    return;
  }
  const nasta: SparatMotorJobb = {
    ...job,
    inputHash: String(svar.inputHash || job.inputHash),
    phase: svar.phase,
    phaseText: svar.phaseText,
    outcome: svar.outcome,
    stale,
  };
  api.sattMotorJobb?.(nasta);
  if (svar.status === "completed" || svar.status === "failed") {
    stoppaMotorJobbPoll();
    onKlart?.(svar, nasta);
  }
}
