import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import * as XLSX from "xlsx";
import { parseSekoiaRapport } from "@/lib/bb/sekoia";
import { parseMedvind } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import {
  jourPanelModell,
  lasJourDiagnos,
  lasPrecheck,
  lasSamtidighetsbrist,
  vakantaPassText,
  visaJourResursbrist,
} from "@/lib/bb/jourDiagnos";
import { sparaJourResursbrist } from "@/lib/bb/korBemanningsbalans";
import { extraTillMedarbetare, tomExtraResurs, type ExtraResurs } from "@/lib/bb/extraResurs";
import { vcStatusText } from "@/lib/bb/vcFlode";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

function galaxenPersonal(): Medarbetare[] {
  return (medvind?.medarbetare || []).map((m) => ({
    namn: m.namn,
    vakant: m.vakant,
    vikarie: m.vikarie,
    grad: m.grad,
    samordnare: false,
    delegering: true,
    jour: null,
    nattbehorig: true,
    passprofil: "blandat",
    helg: "varannan",
    tidigastStart: "06:30",
    senastSlut: "23:00",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
  }));
}

function payload28() {
  return byggMotorPayload({
    rader: sekoia.rows as Insats[],
    medarbetare: galaxenPersonal(),
    from: "2026-08-03",
    dagar: 28,
    timkostnad: 270,
    schemaPass: [],
  });
}

const jourDiag = {
  jour: {
    requiredJourSlots: 28,
    coverableWithRegisteredStaff: 19,
    minimumExternalJourSlots: 9,
    jourCapacityShortfallDetected: true,
    externalDatesAreProvenUnique: false,
    blockingRules: ["jourFloor", "JOUR_4W", "JOUR_MONTH"],
    openJourShiftsInFore: [{ date: "2026-08-08", start: "23:00", end: "06:30", matchingOpenJourShift: true }],
    uncoveredJourWindows: [],
    userMessage: "Obligatorisk jour kan inte bemannas med registrerad personal.",
  },
};

describe("P0 28d A: occurrences", () => {
  it("Galaxen 28d har 2541 insatser och begär tak 4000 så input släpps in", () => {
    const r = payload28();
    expect(r.info.insatser).toBe(2541);
    const limits = r.payload.limits as { maxOccurrences?: number; maxSupportCombinations?: number } | undefined;
    expect(limits?.maxOccurrences).toBe(4000);
    expect(limits?.maxSupportCombinations).toBe(250000);
    expect(r.info.insatser).toBeLessThanOrEqual(4000);
  });
});

describe("P0 28d B: jourbrist i UI", () => {
  it("JOUR_CAPACITY_SHORTFALL visas som Resursbrist identifierad, inte generellt motorfel", () => {
    const d = lasJourDiagnos(jourDiag);
    expect(visaJourResursbrist(d)).toBe(true);
    const m = jourPanelModell(d);
    expect(m.visa).toBe(true);
    expect(m.kompletteraCta).toBe("Komplettera resurs");
    expect(m.ytterligareJourpass).toBe(9);
    expect(m.jourBristRad).toBe("Jour: minst 9 pass saknar möjlig resurs");
    expect(vcStatusText("INFEASIBLE", { jourResursbrist: true })).not.toMatch(/INFEASIBLE/i);
    expect(vcStatusText("INFEASIBLE", { jourResursbrist: true })).toMatch(/registrerade resurser/);
  });
});

describe("P0 28d C: samtidighetsbrist separat", () => {
  it("visar behov 10 mot 5 registrerade som egen kapacitetsbrist", () => {
    const pre = lasPrecheck({
      preCheck: [
        {
          code: "INSUFFICIENT_TOTAL_CAPACITY",
          severity: "warning",
          message: "2026-08-24 kl. 08:00–08:05: behov = 10, maximalt tillgängliga = 5.",
          date: "2026-08-24",
          need: 10,
          available: 5,
        },
      ],
    });
    const sam = lasSamtidighetsbrist(pre);
    expect(sam).toHaveLength(1);
    expect(sam[0]?.need).toBe(10);
    expect(sam[0]?.available).toBe(5);
    expect(jourPanelModell(lasJourDiagnos(jourDiag)).samtidighetIngress).toBe(
      "Samtidigt kundbehov överstiger tillgänglig bemanning vissa tider",
    );
  });

  it("sparar preCheck från motorsvar så samtidighet följer med diagnosen", () => {
    const sparade: unknown[] = [];
    const api = { anvandMotorResultat: (res: unknown) => { sparade.push(res); return true; } };
    sparaJourResursbrist(api as never, {
      ok: true,
      status: "INFEASIBLE",
      resourceDiagnostics: jourDiag,
      schemaJson: JSON.stringify({
        solverStatus: "INFEASIBLE",
        preCheck: [{ code: "INSUFFICIENT_TOTAL_CAPACITY", date: "2026-08-24", need: 10, available: 5, message: "x" }],
        resourceDiagnostics: jourDiag,
      }),
    });
    const res = sparade[0] as { resourceDiagnostics: Record<string, unknown> };
    expect(lasSamtidighetsbrist(lasPrecheck(res.resourceDiagnostics))[0]?.need).toBe(10);
  });
});

describe("P0 28d D: vakanta pass", () => {
  it("40 öppna Medvind-pass skapar inte medarbetare eller kapacitet", () => {
    const r = payload28();
    const employees = (r.payload.employees as { resourceType: string }[]) || [];
    const vacant = (r.payload.vacantShifts as unknown[]) || [];
    expect(employees.filter((e) => e.resourceType === "employee")).toHaveLength(5);
    expect(employees.some((e) => e.resourceType === "temporary")).toBe(false);
    expect(r.info.openShifts).toBe(0);
    expect(vakantaPassText(40)).toMatch(/40 öppna Medvind-pass/);
    expect(vakantaPassText(40)).toMatch(/räknas inte som personal/);
    expect(vacant.length === 0 || employees.length === 5).toBe(true);
  });
});

describe("P0 28d E: explicit temporary", () => {
  it("kompletterar som temporary utan automatisk SSG, kompetens eller delegering", () => {
    const blank = tomExtraResurs();
    expect(blank.jour).toBe(false);
    const extra: ExtraResurs = {
      ...blank,
      namn: "Extern jourresurs",
      slag: "extern",
      jour: true,
      timkostnad: 350,
    };
    const m = extraTillMedarbetare(extra);
    expect(m.resourceType).toBe("temporary");
    expect(m.grad).toBe(0);
    expect(m.kompetenser).toEqual([]);
    expect(m.delegering).toBe(false);
    expect(m.nattbehorig).toBe(false);
    expect(m.passprofil).toBe("jour");
    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: [...galaxenPersonal(), m],
      from: "2026-08-03",
      dagar: 28,
      timkostnad: 270,
    });
    const rad = (r.payload.employees as { resourceType: string; ssg: number; skills: string[]; jour: boolean; night: boolean }[])
      .find((e) => e.resourceType === "temporary");
    expect(rad?.ssg).toBe(0);
    expect(rad?.skills.every((s) => s.startsWith("kund:"))).toBe(true);
    expect(rad?.skills).not.toContain("undersköterska");
    expect(rad?.jour).toBe(true);
    expect(rad?.night).toBe(false);
  });
});
