import { describe, it, expect } from "vitest";
import {
  EXPLICIT_EXTERN_RESURS_FALT,
  harHardJourbrist,
  harMjukKundbrist,
  jourHuvudtext,
  jourPanelModell,
  lasJourDiagnos,
  lasJourDiagnosFranMotorSvar,
  visaJourResursbrist,
} from "@/lib/bb/jourDiagnos";
import { vcStatusText, balansKanGodkannas } from "@/lib/bb/vcFlode";
import { sparaJourResursbrist } from "@/lib/bb/korBemanningsbalans";
import { tolkaMotorSchema } from "@/lib/bb/motorResultat";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const galaxenLiknande = {
  jour: {
    requiredJourSlots: 14,
    coverableWithRegisteredStaff: 11,
    minimumExternalJourSlots: 3,
    jourCapacityShortfallDetected: true,
    externalDatesAreProvenUnique: false,
    diagnosticExternalDates: ["2026-08-14", "2026-08-15", "2026-08-16"],
    blockingRules: ["jourFloor", "JOUR_4W", "JOUR_MONTH"],
    openJourShiftsInFore: [{ date: "2026-08-08", start: "23:00", end: "06:30", matchingOpenJourShift: true }],
    uncoveredJourWindows: [{ date: "2026-08-08", start: "23:00", end: "06:30", matchingOpenJourShift: true }],
    userMessage: "Obligatorisk jour kan inte bemannas med registrerad personal.",
  },
};

describe("UI-JOUR resursbristpanel", () => {
  it("UI-JOUR-A: minimumExternalJourSlots=0 ger ingen bristpanel", () => {
    const d = lasJourDiagnos({
      jour: { requiredJourSlots: 7, coverableWithRegisteredStaff: 7, minimumExternalJourSlots: 0, jourCapacityShortfallDetected: false },
    });
    expect(visaJourResursbrist(d)).toBe(false);
    expect(jourPanelModell(d).visa).toBe(false);
  });

  it("UI-JOUR-B: panelen visar 14 / 11 / 3 från datan, inte hårdkodat", () => {
    const d = lasJourDiagnos(galaxenLiknande);
    const m = jourPanelModell(d);
    expect(m.visa).toBe(true);
    expect(m.jourpassBehov).toBe(14);
    expect(m.mojligaMedRegistrerad).toBe(11);
    expect(m.ytterligareJourpass).toBe(3);
    expect(m.huvud).toContain("14 jourpass");
    expect(m.huvud).toContain("högst 11");
    expect(m.kompletteraCta).toBe("Komplettera resurs");
    expect(m.kompletteraHjalp).toMatch(/Du anger vilken faktisk resurs/);
  });

  it("UI-JOUR-C: osäkra datum listas inte som enda möjliga externa nätter", () => {
    const m = jourPanelModell(lasJourDiagnos(galaxenLiknande));
    expect(m.datumOsakra).toBe(true);
    expect(m.datumVarning).toMatch(/beror på hur resterande jour fördelas/);
    expect(m.huvud).not.toMatch(/2026-08-14/);
    expect(m.datumVarning).not.toMatch(/måste/);
  });

  it("UI-JOUR-D: öppet Jo är Före-information, inte bemanning", () => {
    const m = jourPanelModell(lasJourDiagnos(galaxenLiknande));
    expect(m.openFore).toMatch(/öppna Jo-pass i Före/);
    expect(m.openFore).toMatch(/inte tillgänglig bemanning/);
  });

  it("UI-JOUR-E: hard jourbrist och otäckt kundbehov är två problemtyper", () => {
    const d = lasJourDiagnos(galaxenLiknande);
    expect(harHardJourbrist([{ rule: "JOUR_CAPACITY_SHORTFALL" }], d)).toBe(true);
    expect(harMjukKundbrist({ tacktBehovPct: 61.6, obemannadeAntal: 12 })).toBe(true);
    expect(harMjukKundbrist({ ofullstandigUtanSchema: true, tacktBehovPct: null })).toBe(false);
    const reasons = balansKanGodkannas({
      tacktBehovPct: 61.6,
      hardViolations: 1,
      jourResursbrist: true,
    }).reasons;
    expect(reasons.some((r) => /ytterligare resurs/.test(r))).toBe(true);
    expect(reasons.some((r) => /kundinsatser är ännu inte bemannade/.test(r))).toBe(true);
    expect(reasons.join(" ")).not.toMatch(/underbemanning/i);
  });

  it("UI-JOUR-F: verksamhetsförklaring, inte teknisk solverstatus", () => {
    const text = vcStatusText("INFEASIBLE", { jourResursbrist: true });
    expect(text).not.toMatch(/INFEASIBLE/i);
    expect(text).toMatch(/registrerade resurser/);
    const m = jourPanelModell(lasJourDiagnos(galaxenLiknande));
    expect(m.ingress).toMatch(/kan inte skapas fullt ut/);
    expect(m.hardJourText).toMatch(/färdigställas utan ytterligare resurs/);
  });

  it("behåller resourceDiagnostics genom schema-JSON", () => {
    const schema = tolkaMotorSchema(
      JSON.stringify({
        solverStatus: "INFEASIBLE",
        explanation: "Giltigt Balans-schema kan inte skapas.",
        shifts: [],
        assignments: [],
        uncovered: [],
        resourceDiagnostics: galaxenLiknande,
      }),
      { medarbetare: {}, insatser: {} },
    );
    expect(schema?.resourceDiagnostics).toEqual(galaxenLiknande);
    const franSvar = lasJourDiagnosFranMotorSvar({
      resourceDiagnostics: galaxenLiknande,
      schemaJson: JSON.stringify({ resourceDiagnostics: galaxenLiknande }),
    });
    expect(franSvar?.minimumExternalJourSlots).toBe(3);
  });

  it("sparar diagnos i stället för att skapa schema när jourbrist finns", () => {
    const sparade: unknown[] = [];
    const api = { anvandMotorResultat: (res: unknown) => { sparade.push(res); return true; } };
    const ok = sparaJourResursbrist(api as never, {
      ok: true,
      status: "INFEASIBLE",
      forklaring: "Obligatorisk jour kan inte bemannas med registrerad personal.",
      resourceDiagnostics: galaxenLiknande,
      summary: { hardViolations: [{ rule: "JOUR_CAPACITY_SHORTFALL", message: "x" }] },
    });
    expect(ok).toBe(true);
    const res = sparade[0] as { ofullstandig?: boolean; pass: unknown[]; resourceDiagnostics: unknown };
    expect(res.ofullstandig).toBe(true);
    expect(res.pass).toEqual([]);
    expect(res.resourceDiagnostics).toEqual(galaxenLiknande);
  });

  it("föreslår fält för framtida explicit extern resurs utan att skapa pool", () => {
    expect(EXPLICIT_EXTERN_RESURS_FALT).toEqual(expect.arrayContaining([
      "antal",
      "tillgangligaDatum",
      "jourbehorighet",
      "nattbehorighet",
      "kompetens",
      "helg",
      "timkostnad",
      "ssgEllerTimtak",
    ]));
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../src/lib/bb/korBemanningsbalans.ts"), "utf8");
    expect(src).not.toMatch(/temp_pool.*=.*true/);
    expect(src).toContain("sparaJourResursbrist");
  });
});
