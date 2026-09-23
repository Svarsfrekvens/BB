/** Klient för asynkron motor-jobb. Ingen ny solverlogik. */

import { hamtaMotorJobb, startaMotorJobb, type MotorJobbSvar } from "./motor.functions";
import type { VyApi } from "./vy";

export type SparatMotorJobb = {
  id: string;
  inputHash: string;
  underlagHash: string;
  started: string;
  phase?: string | undefined;
  phaseText?: string | undefined;
  outcome?: string | null | undefined;
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

export function fasSteg(phase: string | undefined, phaseText?: string) {
  const raw = String(phase || "queued");
  const nu = raw === "improving" ? "solving" : raw;
  const idx = FASER.indexOf(nu as (typeof FASER)[number]);
  const solvingLabel = phaseText === "Förbättrar balans" || raw === "improving" ? "Förbättrar balans" : "Skapar balans";
  return [
    { id: "preparing", label: "Förbereder underlag", klar: idx > 0 || nu === "completed" },
    { id: "checking", label: "Förbereder underlag", klar: idx > 1 || nu === "completed" },
    { id: "solving", label: solvingLabel, klar: idx > 2 || nu === "completed", pa: nu === "solving" },
    { id: "validating", label: "Kontrollerar resultat", klar: nu === "completed", pa: nu === "validating" },
  ];
}

export const AVBRUTEN_JOBB_TEXT = "Beräkningen avbröts. Skapa balans igen.";

export type PollBeslut = {
  nasta: SparatMotorJobb;
  stoppa: boolean;
  kallaKlart: boolean;
  bevaraBalans: boolean;
};

export function hanteraHamtaJobbSvar(
  svar: MotorJobbSvar,
  job: SparatMotorJobb,
  underlagHashNu: string,
): PollBeslut {
  const stale = underlagHashNu !== job.underlagHash;
  if (!svar.ok) {
    const okand =
      svar.status === "404" || /hittades inte|försvunnit/i.test(String(svar.meddelande || ""));
    if (okand) {
      return {
        nasta: {
          ...job,
          stale,
          phase: "failed",
          outcome: "tekniskt_fel",
          phaseText: AVBRUTEN_JOBB_TEXT,
        },
        stoppa: true,
        kallaKlart: false,
        bevaraBalans: true,
      };
    }
    return {
      nasta: {
        ...job,
        stale,
        phaseText: "Kontakten avbröts – kontrollerar om beräkningen fortfarande pågår",
      },
      stoppa: false,
      kallaKlart: false,
      bevaraBalans: true,
    };
  }
  const nasta: SparatMotorJobb = {
    ...job,
    inputHash: String(svar.inputHash || job.inputHash),
    phase: svar.phase,
    phaseText: svar.phaseText,
    outcome: svar.outcome,
    stale,
  };
  const status = String(svar.status || svar.phase || "");
  const completed = status === "completed";
  const failed = status === "failed";
  const terminal = completed || failed;
  return {
    nasta,
    stoppa: terminal,
    kallaKlart: Boolean(completed && svar.result && !stale),
    bevaraBalans: true,
  };
}

export function skaAtterupptaSparatJobb(job: SparatMotorJobb | null | undefined) {
  if (!job?.id) return false;
  return job.phase !== "completed" && job.phase !== "failed";
}

export function pollarMotorJobb() {
  return pollTimer != null;
}

export function resetMotorJobbPollForTest() {
  stoppaMotorJobbPoll();
  onKlart = null;
}

export function kopplaAtterupptning(
  getVy: () => { api: VyApi | null; state: unknown },
  subscribe: (f: () => void) => () => void,
  atteruppta: (api: VyApi, state: unknown) => void,
) {
  const forsok = () => {
    const v = getVy();
    if (v.api && v.state != null) atteruppta(v.api, v.state);
  };
  forsok();
  return subscribe(forsok);
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
  const beslut = hanteraHamtaJobbSvar(svar, job, nuHash);
  api.sattMotorJobb?.(beslut.nasta);
  if (beslut.stoppa) {
    stoppaMotorJobbPoll();
    if (beslut.kallaKlart) onKlart?.(svar, beslut.nasta);
  }
}
