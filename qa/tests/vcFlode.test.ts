import { describe, it, expect } from "vitest";
import {
  FORE_EFTER_NYCKLAR,
  PROCESS_STEG,
  TRE_OMRADEN_RUBRIKER,
  filtreraJamforRader,
  jamforTon,
  kundUnderlagStatus,
  lasMotorSummary,
  oversiktVisaLage,
  processStegLagen,
  skapaBalansHinder,
  vcStatusText,
} from "@/lib/bb/vcFlode";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const rot = join(dirname(fileURLToPath(import.meta.url)), "../..");

describe("processsteg", () => {
  it("har sex steg med pilar i UI, inte ett progress-streck", () => {
    expect(PROCESS_STEG.map((s) => s.label)).toEqual([
      "Kundbehov",
      "Medarbetare",
      "Skapa bemanningsbalans",
      "Granska",
      "Godkänn",
      "Uppföljning",
    ]);
    const src = readFileSync(join(rot, "src/components/bb/ProcessFlode.tsx"), "utf8");
    expect(src).toContain("→");
    expect(src).not.toMatch(/Progress/);
    expect(src).toContain("Ej påbörjad");
    expect(src).toContain("Pågående");
    expect(src).toContain("Klar");
    expect(src).toContain("Varning");
    expect(src).toContain("Blockerad");
    expect(src).toContain("sm:inline");
  });

  it("sätter blockerad när skapa inte får köras", () => {
    const steg = processStegLagen({
      aktivTab: "hem",
      kundGodkand: false,
      medarbetareOk: false,
      harResultat: false,
      harVarning: false,
      blockeradSkapa: true,
    });
    expect(steg.find((s) => s.id === "motor")?.lage).toBe("blockerad");
    expect(steg.find((s) => s.id === "kundbehov")?.lage).toBe("ej");
  });

  it("varnar på granska när resultat finns med varning", () => {
    const steg = processStegLagen({
      aktivTab: "resultat",
      kundGodkand: true,
      medarbetareOk: true,
      harResultat: true,
      harVarning: true,
      blockeradSkapa: false,
    });
    expect(steg.find((s) => s.id === "resultat")?.lage).toBe("varning");
  });
});

describe("CTA skapa bemanningsbalans", () => {
  it("är inaktiv utan godkänt kundbehov", () => {
    const h = skapaBalansHinder({
      kundGodkand: false,
      harUnderlag: true,
      medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: true }],
    });
    expect(h.aktiv).toBe(false);
    expect(h.skal).toContain("Kundbehovet är inte godkänt");
  });

  it("räknar medarbetare utan arbetstidsmodell", () => {
    const h = skapaBalansHinder({
      kundGodkand: true,
      harUnderlag: true,
      medarbetare: [
        { namn: "Anna" },
        { namn: "Bo" },
        { namn: "Cia", workTimeModelId: "helgfri-40", nattbehorig: true },
      ],
    });
    expect(h.aktiv).toBe(false);
    expect(h.skal.some((s) => s.includes("2 medarbetare saknar arbetstidsmodell"))).toBe(true);
  });

  it("varnar när nattbehörighet saknas helt", () => {
    const h = skapaBalansHinder({
      kundGodkand: true,
      harUnderlag: true,
      medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: false }],
    });
    expect(h.skal).toContain("Nattbehörighet saknas");
    expect(h.aktiv).toBe(false);
  });

  it("är aktiv när underlaget räcker", () => {
    const h = skapaBalansHinder({
      kundGodkand: true,
      harUnderlag: true,
      medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: true }],
    });
    expect(h.aktiv).toBe(true);
    expect(h.skal).toEqual([]);
  });
});

describe("summary-adapter", () => {
  it("mappar motorns summary-fält utan egen solverdiagnostik", () => {
    const s = lasMotorSummary({
      summary: {
        status: "FEASIBLE",
        coveragePercent: 100,
        customerNearPercent: 32.1,
        cost: 1234500,
        hardViolations: [{ rule: "rest", message: "vila" }],
        warnings: [{ message: "natt" }],
        changedShiftCount: 4,
        lockedShiftCount: 2,
        explanationSummary: "Täckning först.",
        performanceSummary: "9s",
      },
    });
    expect(s).toMatchObject({
      status: "FEASIBLE",
      coveragePercent: 100,
      customerNearPercent: 32.1,
      cost: 1234500,
      changedShiftCount: 4,
      lockedShiftCount: 2,
      explanationSummary: "Täckning först.",
    });
    expect(s?.hardViolations).toHaveLength(1);
    expect(s?.warnings).toHaveLength(1);
    expect(vcStatusText("INFEASIBLE")).not.toMatch(/INFEASIBLE/);
    expect(vcStatusText("FEASIBLE")).toMatch(/giltigt/i);
  });
});

describe("Rätt resurser i rätt tid", () => {
  it("används som rubrik, inte Ekonomi", () => {
    expect(TRE_OMRADEN_RUBRIKER).toContain("Rätt resurser i rätt tid");
    expect(TRE_OMRADEN_RUBRIKER.join(" ")).not.toMatch(/Ekonomi/);
    const tre = readFileSync(join(rot, "src/components/bb/TreOmraden.tsx"), "utf8");
    expect(tre).toContain("Rätt resurser i rätt tid");
    expect(tre).toContain("lg:grid-cols-3");
    const eko = readFileSync(join(rot, "src/components/bb/Ekonomi.tsx"), "utf8");
    expect(eko).toContain("Rätt resurser i rätt tid");
  });
});

describe("före/efter och polaritet", () => {
  it("visar bara relevanta nyckeltal med verksamhetsnära namn", () => {
    const rader = filtreraJamforRader([
      { namn: "Täckt behov", fore: "80 %", efter: "90 %", forandring: "+10 %", riktning: "upp" },
      { namn: "Personalkostnad", fore: "10", efter: "9", forandring: "−1", riktning: "upp" },
      { namn: "Planerade personaltimmar", fore: "100", efter: "80", forandring: "−20", riktning: "upp" },
      { namn: "Överbemanning", fore: "10", efter: "4", forandring: "−6", riktning: "upp" },
    ]);
    expect(rader.map((r) => r.namn)).toEqual(["Täckt behov", "Schemakostnad", "Överkapacitet"]);
    expect(FORE_EFTER_NYCKLAR).toContain("Täckt behov");
  });

  it("markerar inte lägre bemanning som bra när täckningen sjunker", () => {
    expect(jamforTon({ namn: "Överkapacitet", riktning: "upp", tackningSank: true })).toBe("varn");
    expect(jamforTon({ namn: "Täckt behov", riktning: "upp", tackningSank: false })).toBe("bra");
    expect(jamforTon({ namn: "Täckt behov", riktning: "ner", tackningSank: true })).toBe("varn");
  });
});

describe("varningar, hårda brott, ändrade och låsta pass", () => {
  it("läser counts från summary", () => {
    const s = lasMotorSummary({
      summary: {
        status: "FEASIBLE",
        hardViolations: [{}, {}],
        warnings: [{}],
        changedShiftCount: 7,
        lockedShiftCount: 3,
        cost: 0,
      },
    });
    expect(s?.hardViolations).toHaveLength(2);
    expect(s?.warnings).toHaveLength(1);
    expect(s?.changedShiftCount).toBe(7);
    expect(s?.lockedShiftCount).toBe(3);
  });
});

describe("tomma, laddande och fel-lägen", () => {
  it("väljer visningsläge utan att räkna om KPI", () => {
    expect(oversiktVisaLage({ laddar: true })).toBe("laddar");
    expect(oversiktVisaLage({ fel: "saknas" })).toBe("fel");
    expect(oversiktVisaLage({ tom: true })).toBe("tom");
    expect(oversiktVisaLage({})).toBe("klar");
  });

  it("kundunderlag visar klar, kompletteras eller förändrad", () => {
    expect(kundUnderlagStatus({ godkand: true }).text).toBe("Klar");
    expect(kundUnderlagStatus({ godkand: false }).text).toBe("Behöver kompletteras");
    expect(kundUnderlagStatus({ godkand: true, redigerad: true }).text).toBe("Förändrad sedan senaste godkännande");
  });
});
