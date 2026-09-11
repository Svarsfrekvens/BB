import { describe, it, expect } from "vitest";
import { rymInomPass } from "@/lib/bb/kpi";
import { analysera, jamfor } from "@/lib/bb/modell";
import type { DatumPass } from "@/lib/bb/medvind";
import type { Insats } from "@/lib/bb/typer";

function pass(del: Partial<DatumPass> = {}): DatumPass {
  return {
    id: "p1",
    namn: "Anna",
    vakant: false,
    vikarie: false,
    vecka: 1,
    dag: 0,
    start: "08:00",
    slut: "16:00",
    kod: "Ar",
    jour: false,
    natt: false,
    timmar: 8,
    datum: "2026-09-07",
    ...del,
  };
}

function rad(del: Partial<Insats> = {}): Insats {
  return {
    id: "r1",
    datum: "2026-09-07",
    kund: "Kund 1",
    insats: "Stöd",
    start: "09:00",
    slut: "15:00",
    minuter: 360,
    tvaPersoner: false,
    flyttbar: false,
    status: "Utförd",
    kallrad: 1,
    ...del,
  };
}

describe("passkapacitet för inom_pass", () => {
  it("Test 1 via analysera: 8 h schema, 6 h kund, 30 min journal → 81,25 %", () => {
    const lage = analysera({
      rader: [rad()],
      pass: [pass()],
      fran: "2026-09-07",
      till: "2026-09-07",
      timkostnad: 270,
      extraInomPassKundnaraH: 0.5,
    });
    expect(lage.schematidH).toBe(8);
    expect(lage.kundnaraH).toBeCloseTo(6.5, 5);
    expect(lage.ejKundnaraH).toBeCloseTo(1.5, 5);
    expect(lage.kundnaraPct).toBeCloseTo(81.25, 5);
    expect(lage.inomPassOverflowH).toBeCloseTo(0, 5);
    expect(lage.kundnaraH).toBeLessThanOrEqual(lage.schematidH);
  });

  it("fullt pass släpper inte in extra GP som osynlig tid", () => {
    const lage = analysera({
      rader: [rad({ start: "08:00", slut: "16:00", minuter: 480 })],
      pass: [pass()],
      fran: "2026-09-07",
      till: "2026-09-07",
      timkostnad: 270,
      extraInomPassKundnaraH: 0.5,
    });
    expect(lage.schematidH).toBe(8);
    expect(lage.kundnaraH).toBeLessThanOrEqual(8);
    expect(lage.kundnaraH).toBeCloseTo(8, 5);
    expect(lage.inomPassOverflowH).toBeGreaterThan(0);
    expect(lage.modellFel).toBe(true);
  });

  it("rymmaInomPass kapar 3 h extra till 2 h kvar", () => {
    const r = rymInomPass({ schematidH: 8, direktKundnaraH: 6, inomPassKundnaraH: 3 });
    expect(r.kundnaraH).toBeCloseTo(8, 5);
    expect(r.rymdKundnaraH).toBeCloseTo(2, 5);
    expect(r.overflowH).toBeCloseTo(1, 5);
    expect(r.platsBrist).toBe(true);
  });

  it("obemannat kundbehov och dimensionerande gap är olika fält", () => {
    const lage = analysera({
      rader: [rad()],
      pass: [pass()],
      fran: "2026-09-07",
      till: "2026-09-07",
      timkostnad: 270,
    });
    expect(lage.obemannatKundbehovH).toBeCloseTo(Math.max(0, lage.kundbehovH - lage.bemannatKundbehovH), 5);
    expect(lage.otacktDimensionerandeResursH).toBe(lage.obemannatH);
    const fe = jamfor(lage, lage, [], { h: (x) => String(x), kr: (x) => String(x), pct: (x) => String(x) });
    expect(fe.tabell.some((r) => r.namn === "Obemannat kundbehov")).toBe(true);
    expect(fe.tabell.some((r) => r.namn === "Otäckt dimensionerande resursbehov")).toBe(true);
    expect(fe.tabell.some((r) => r.namn === "Underbemanning (obemannat behov)")).toBe(false);
  });
});
