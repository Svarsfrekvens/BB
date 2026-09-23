import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import {
  AVBRUTEN_JOBB_TEXT,
  hanteraHamtaJobbSvar,
  kopplaAtterupptning,
  pollarMotorJobb,
  resetMotorJobbPollForTest,
  skaAtterupptaSparatJobb,
  startaMotorJobbPoll,
  type SparatMotorJobb,
} from "@/lib/bb/motorJobb";
import { balansKanGodkannas } from "@/lib/bb/vcFlode";
import { hamtaMotorJobb, startaMotorJobb } from "@/lib/bb/motor.functions";

vi.mock("@/lib/bb/motor.functions", () => ({
  hamtaMotorJobb: vi.fn(),
  startaMotorJobb: vi.fn(),
  motorStatus: vi.fn(),
  optimeraMedMotor: vi.fn(),
  granskaMedMotor: vi.fn(),
}));

const hamta = vi.mocked(hamtaMotorJobb);
const postJobb = vi.mocked(startaMotorJobb);

const jobSolving: SparatMotorJobb = {
  id: "6f7a95ed-bfca-4607-9a82-d58137b8aa29",
  inputHash: "abc",
  underlagHash: "u1",
  started: "2026-08-03T00:00:00.000Z",
  phase: "solving",
  phaseText: "Skapar balans",
};

function fakeApi(job: SparatMotorJobb | null) {
  let nu = job;
  const satt = vi.fn((j: SparatMotorJobb | null) => {
    nu = j;
  });
  return {
    motorJobb: () => nu,
    sattMotorJobb: satt,
    underlagFingeravtryck: () => "u1",
    anvandMotorResultat: vi.fn(() => true),
    schemaPassOriginal: () => [],
    skapa: vi.fn(),
  };
}

describe("resume efter browser reload", () => {
  beforeEach(() => {
    resetMotorJobbPollForTest();
    hamta.mockReset();
    postJobb.mockReset();
  });
  afterEach(() => {
    resetMotorJobbPollForTest();
    vi.useRealTimers();
  });

  it("A: hydration startar poll först när api finns, samma jobId, ingen POST", () => {
    const atteruppta = vi.fn();
    let vy: { api: ReturnType<typeof fakeApi> | null; state: Record<string, unknown> | null } = {
      api: null,
      state: null,
    };
    let lyssna: (() => void) | null = null;
    kopplaAtterupptning(
      () => vy,
      (f) => {
        lyssna = f;
        return () => {
          lyssna = null;
        };
      },
      atteruppta,
    );
    expect(atteruppta).not.toHaveBeenCalled();
    const api = fakeApi(jobSolving);
    vy = { api, state: { period: { from: "2026-08-03" } } };
    lyssna?.();
    expect(atteruppta).toHaveBeenCalledTimes(1);
    expect(atteruppta.mock.calls[0]?.[0]).toBe(api);
    expect(postJobb).not.toHaveBeenCalled();
  });

  it("A: reload + running fortsätter GET på samma jobId utan POST", async () => {
    vi.useFakeTimers();
    hamta.mockResolvedValue({
      ok: true,
      status: "running",
      jobId: jobSolving.id,
      phase: "solving",
      phaseText: "Skapar balans",
      outcome: null,
    });
    const api = fakeApi(jobSolving);
    const onKlart = vi.fn();
    startaMotorJobbPoll(api as never, onKlart);
    await Promise.resolve();
    expect(hamta).toHaveBeenCalledTimes(1);
    expect(hamta.mock.calls[0]?.[0]).toEqual({ data: { jobId: jobSolving.id } });
    expect(postJobb).not.toHaveBeenCalled();
    expect(onKlart).not.toHaveBeenCalled();
    expect(pollarMotorJobb()).toBe(true);
    await vi.advanceTimersByTimeAsync(2000);
    expect(hamta).toHaveBeenCalledTimes(2);
    expect(postJobb).not.toHaveBeenCalled();
  });

  it("B: reload + completed applicerar result, sätter balans_klar och stoppar poll", async () => {
    hamta.mockResolvedValue({
      ok: true,
      status: "completed",
      jobId: jobSolving.id,
      phase: "completed",
      phaseText: "Balans klar",
      outcome: "balans_klar",
      result: {
        ok: true,
        status: "FEASIBLE",
        schemaJson: JSON.stringify({
          solverStatus: "FEASIBLE",
          shifts: [{ id: "s1", employeeId: "e1", date: "2026-08-03", start: "07:00", end: "16:00", type: "day" }],
          assignments: [],
        }),
      },
    });
    const api = fakeApi(jobSolving);
    const onKlart = vi.fn();
    startaMotorJobbPoll(api as never, onKlart);
    await Promise.resolve();
    expect(onKlart).toHaveBeenCalledTimes(1);
    expect(onKlart.mock.calls[0]?.[1].outcome).toBe("balans_klar");
    expect(onKlart.mock.calls[0]?.[1].phase).toBe("completed");
    expect(pollarMotorJobb()).toBe(false);
    expect(api.sattMotorJobb).toHaveBeenCalled();
    const nasta = api.sattMotorJobb.mock.calls.at(-1)?.[0];
    expect(nasta?.phase).toBe("completed");
  });

  it("C: completed 100 % ger Godkänn balans", () => {
    const b = hanteraHamtaJobbSvar(
      {
        ok: true,
        status: "completed",
        phase: "completed",
        outcome: "balans_klar",
        result: { ok: true, status: "FEASIBLE" },
      },
      jobSolving,
      "u1",
    );
    expect(b.kallaKlart).toBe(true);
    expect(b.nasta.outcome).toBe("balans_klar");
    expect(
      balansKanGodkannas({ tacktBehovPct: 100, hardViolations: 0, saknadeKompetenskrav: 0 }).ok,
    ).toBe(true);
  });

  it("D: reload + failed stoppar poll och kallar inte resultathantering", async () => {
    hamta.mockResolvedValue({
      ok: true,
      status: "failed",
      phase: "failed",
      phaseText: "Beräkningen avbröts när tjänsten startades om. Skapa balans igen.",
      outcome: "tekniskt_fel",
      result: { ok: true, status: "FEASIBLE", schemaJson: "{\"shifts\":[{}]}" },
    });
    const api = fakeApi(jobSolving);
    const onKlart = vi.fn();
    startaMotorJobbPoll(api as never, onKlart);
    await Promise.resolve();
    expect(onKlart).not.toHaveBeenCalled();
    expect(pollarMotorJobb()).toBe(false);
    const nasta = api.sattMotorJobb.mock.calls.at(-1)?.[0];
    expect(nasta?.phase).toBe("failed");
    expect(nasta?.phaseText).toMatch(/avbröts|Skapa balans/i);
  });

  it("E: reload + 404 stoppar poll utan evig retry och behåller Balans", async () => {
    hamta.mockResolvedValue({
      ok: false,
      status: "404",
      meddelande: "Beräkningen hittades inte. Den kan ha försvunnit vid omstart.",
    });
    const api = fakeApi(jobSolving);
    const onKlart = vi.fn();
    startaMotorJobbPoll(api as never, onKlart);
    await Promise.resolve();
    expect(onKlart).not.toHaveBeenCalled();
    expect(pollarMotorJobb()).toBe(false);
    const nasta = api.sattMotorJobb.mock.calls.at(-1)?.[0];
    expect(nasta?.phaseText).toBe(AVBRUTEN_JOBB_TEXT);
    const b = hanteraHamtaJobbSvar(
      { ok: false, status: "404", meddelande: "Beräkningen hittades inte." },
      jobSolving,
      "u1",
    );
    expect(b.stoppa).toBe(true);
    expect(b.bevaraBalans).toBe(true);
    expect(b.kallaKlart).toBe(false);
  });

  it("F: stale inputHash applicerar inte gammalt resultat", () => {
    const b = hanteraHamtaJobbSvar(
      {
        ok: true,
        status: "completed",
        inputHash: "abc",
        phase: "completed",
        outcome: "balans_klar",
        result: { ok: true, status: "FEASIBLE" },
      },
      jobSolving,
      "annat-underlag",
    );
    expect(b.nasta.stale).toBe(true);
    expect(b.stoppa).toBe(true);
    expect(b.kallaKlart).toBe(false);
    expect(b.bevaraBalans).toBe(true);
  });

  it("terminalt sparat jobb startas inte om efter reload", () => {
    expect(skaAtterupptaSparatJobb({ ...jobSolving, phase: "completed" })).toBe(false);
    expect(skaAtterupptaSparatJobb({ ...jobSolving, phase: "failed" })).toBe(false);
    expect(skaAtterupptaSparatJobb(jobSolving)).toBe(true);
    expect(skaAtterupptaSparatJobb(null)).toBe(false);
  });

  it("reload nollställer inte sparad Balans bara för att den är optimerad", () => {
    const src = readFileSync(new URL("../../src/lib/bb/app.ts", import.meta.url), "utf8");
    expect(src).not.toMatch(/state\.optimerat\) \{ state\.optimerat = false; state\.balans = null/);
  });
});
