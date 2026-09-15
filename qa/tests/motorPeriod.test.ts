import { describe, it, expect } from "vitest";
import { delaPeriod, HELPERIOD_FONSTER, SMALA_FONSTER } from "@/lib/bb/motorPeriod";

function rader(from: string, dagar: number, perDag: number) {
  const ut: { date: string }[] = [];
  const t0 = Date.parse(from + "T12:00:00Z");
  for (let i = 0; i < dagar; i++) {
    const d = new Date(t0 + i * 864e5).toISOString().slice(0, 10);
    for (let n = 0; n < perDag; n++) ut.push({ date: d });
  }
  return ut;
}

describe("delaPeriod", () => {
  it("skickar 7 dagar som ett fönster med defaultgränser", () => {
    const ins = rader("2026-08-03", 7, 90);
    const f = delaPeriod("2026-08-03", "2026-08-09", ins);
    expect(f).toHaveLength(1);
    expect(f[0]).toMatchObject({ from: "2026-08-03", to: "2026-08-09", dagar: 7, insatser: 630 });
  });

  it("skickar 28 dagar som ett fönster när insatserna ryms i motortaket", () => {
    const ins = rader("2026-08-03", 28, 90);
    const f = delaPeriod("2026-08-03", "2026-08-30", ins);
    expect(ins.length).toBeLessThanOrEqual(HELPERIOD_FONSTER.maxInsatser);
    expect(f).toHaveLength(1);
    expect(f[0]?.dagar).toBe(28);
  });

  it("kan fortfarande delas i 3-dagarsfönster via SMALA_FONSTER", () => {
    const ins = rader("2026-08-03", 7, 90);
    const f = delaPeriod("2026-08-03", "2026-08-09", ins, SMALA_FONSTER);
    expect(f.length).toBeGreaterThan(1);
    expect(f.every((x) => x.dagar <= 3)).toBe(true);
    expect(f.every((x) => x.insatser <= 320)).toBe(true);
  });
});
