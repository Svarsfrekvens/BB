import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/app";
import { parseMedvind } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { STYRANDE_VILLKOR } from "@/lib/bb/modell";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

function villkorTal(namn: string, standard: number) {
  for (const g of STYRANDE_VILLKOR) {
    for (const rad of g.villkor) {
      if (rad[0] === namn) {
        const x = parseFloat(String(rad[1] ?? "").replace(",", "."));
        return Number.isFinite(x) ? x : standard;
      }
    }
  }
  return standard;
}

function reglerFranVillkor() {
  return {
    maxShiftHours: villkorTal("Långpass – röd varning", 12),
    maxConsecutiveDays: Math.round(villkorTal("Max arbetsdagar i följd", 5)),
  };
}

function tillMedarbetare(): Medarbetare[] {
  return (medvind?.medarbetare || []).map((m) => ({
    namn: m.namn,
    vakant: m.vakant,
    vikarie: m.vikarie,
    grad: m.grad,
    samordnare: false,
    delegering: true,
    jour: false,
    nattbehorig: true,
    passprofil: "",
    helg: "varannan",
    tidigastStart: "",
    senastSlut: "",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "",
  }));
}

function payload(dagar: number) {
  return byggMotorPayload({
    rader: (sekoia.rows as Insats[]),
    medarbetare: tillMedarbetare(),
    from: "2026-08-03",
    dagar,
    timkostnad: 270,
    regler: reglerFranVillkor(),
  });
}

const KOD_PERSON = /^[A-ZÅÄÖ0-9-]{1,8}$/;
const KOD_KUND = /^Kund \d+$/;

describe("motorPayload ur Galaxen", () => {
  it("employee-koder matchar motorns regex", () => {
    const employees = (payload(7).payload.employees as { code: string }[]) || [];
    expect(employees.length).toBeGreaterThan(0);
    for (const e of employees) expect(e.code).toMatch(KOD_PERSON);
  });

  it("kundkoder är 'Kund N'", () => {
    const customers = (payload(7).payload.customers as { code: string }[]) || [];
    expect(customers.length).toBeGreaterThan(0);
    for (const c of customers) expect(c.code).toMatch(KOD_KUND);
  });

  it("Galaxen skapar inga V-koder från Ingen placerad", () => {
    const employees = (payload(7).payload.employees as { code: string; name: string; status: string }[]) || [];
    const vikarier = employees.filter((e) => e.code.startsWith("V") || /^Vikarie \d+$/i.test(e.name));
    expect(vikarier).toEqual([]);
  });

  it("maxShiftHours och maxConsecutiveDays läses ur STYRANDE_VILLKOR, inte 16/7", () => {
    const regler = reglerFranVillkor();
    expect(regler.maxShiftHours).not.toBe(16);
    expect(regler.maxConsecutiveDays).not.toBe(7);
    const r = payload(7).payload.rules as { maxShiftHours: number; maxConsecutiveDays: number };
    expect(r.maxShiftHours).toBe(regler.maxShiftHours);
    expect(r.maxConsecutiveDays).toBe(regler.maxConsecutiveDays);
  });

  it("28 dagar ger overTak true, 7 dagar false", () => {
    expect(payload(28).info.overTak).toBe(true);
    expect(payload(7).info.overTak).toBe(false);
  });

  it("skickar objectiveWeights med standard 50, 2,5 och 500", () => {
    const w = payload(7).payload.objectiveWeights as {
      continuitySek: number;
      spreadSekPerPermille: number;
      uncoveredSekPerMinute: number;
    };
    expect(w.continuitySek).toBe(50);
    expect(w.spreadSekPerPermille).toBe(2.5);
    expect(w.uncoveredSekPerMinute).toBe(500);
  });

  it("skickar rules.jour med 23:00–06:30 alla veckodagar", () => {
    const jour = (payload(7).payload.rules as { jour: { start: string; end: string; weekdays: number[] } }).jour;
    expect(jour).toEqual({ start: "23:00", end: "06:30", weekdays: [1, 2, 3, 4, 5, 6, 7] });
  });

  it("lägger jour-mall och jourFloor när natten saknar arbetspass", () => {
    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: tillMedarbetare(),
      from: "2026-08-03",
      dagar: 7,
      timkostnad: 270,
      mallar: [{ id: "dag", type: "day", start: "07:00", end: "16:00", breaks: [], skills: [] }],
      regler: reglerFranVillkor(),
    });
    const mallar = (r.payload.templates as { type: string; start: string; end: string }[]) || [];
    expect(mallar.some((m) => m.type === "jour" && m.start === "23:00" && m.end === "06:30")).toBe(false);
    expect(r.info.regler.nightFloor).toBe(0);
    expect(r.info.regler.jourFloor).toBe(0);
  });

  it("sänker inte nightFloor eller jourFloor när personalen inte räcker", () => {
    const personer = tillMedarbetare().slice(0, 2).map((p) => ({ ...p, nattbehorig: false, jour: false }));
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 5),
      medarbetare: personer,
      from: "2026-08-03",
      dagar: 7,
      timkostnad: 270,
      regler: { ...reglerFranVillkor(), nightFloor: 2, jourFloor: 1 },
    });
    expect(r.info.regler.nightFloor).toBe(2);
    expect(r.info.regler.jourFloor).toBe(1);
    expect(r.varningar.some((v) => /sänks inte|oförändrat/.test(v))).toBe(true);
  });

  it("nattbehörig utan jour får jour=false", () => {
    const e = (payload(7).payload.employees as { night: boolean; jour: boolean; code: string; profiles: string[] }[])
      .find((x) => x.code.startsWith("M"));
    expect(e?.night).toBe(true);
    expect(e?.jour).toBe(false);
    const mallar = payload(7).payload.templates as { id: string; type: string }[];
    const jourIds = mallar.filter((m) => m.type === "jour").map((m) => m.id);
    expect(e?.profiles.some((id) => jourIds.includes(id))).toBe(false);
  });

  it("skickar datumstyrd helg och veckovila till motorn", () => {
    const r = payload(7);
    const employees = (r.payload.employees as { constraints?: { hard?: { weekendMode?: string } } }[]) || [];
    const ordinarie = employees.filter((e) => !String((e as { code?: string }).code || "").startsWith("V") && !String((e as { id?: string }).id || "").startsWith("x"));
    expect(ordinarie.length).toBeGreaterThan(1);
    expect(ordinarie.every((e) => e.constraints?.hard?.weekendMode === "every_other")).toBe(true);
    const rules = r.payload.rules as { minWeeklyRestHours: number; withinPassMinutesPerShift: number };
    expect(rules.minWeeklyRestHours).toBe(36);
    expect(rules.withinPassMinutesPerShift).toBe(0);
  });

  it("endast dag i passprofil ger inte nattmall", () => {
    const personer = tillMedarbetare();
    personer[0] = { ...personer[0]!, passprofil: "Dag", nattbehorig: true };
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 20),
      medarbetare: personer.slice(0, 3),
      from: "2026-08-03",
      dagar: 7,
      timkostnad: 270,
      regler: reglerFranVillkor(),
    });
    const e = (r.payload.employees as { name: string; profiles: string[]; constraints: { hard: { allowedTypes?: string[] } } }[])[0];
    const mallar = r.payload.templates as { id: string; type: string }[];
    const nattIds = mallar.filter((m) => m.type === "night" || m.type === "jour").map((m) => m.id);
    expect(e?.constraints.hard.allowedTypes).toEqual(["day"]);
    expect(e?.profiles.some((id) => nattIds.includes(id))).toBe(false);
  });

  it("standard maxDagarIFoljd blir inte hårt maxConsecutiveDays", () => {
    const employees = (payload(7).payload.employees as { constraints?: { hard?: { maxConsecutiveDays?: number } } }[]) || [];
    const ordinarie = employees.filter((e) => !String((e as { id?: string }).id || "").startsWith("x"));
    expect(ordinarie.every((e) => e.constraints?.hard?.maxConsecutiveDays == null)).toBe(true);
  });

  it("minRestDaysInFourWeeks följer styrande villkor och 0 stänger inte av F-01", () => {
    const on = payload(7).payload.rules as { minRestDaysInFourWeeks: number };
    expect(on.minRestDaysInFourWeeks).toBe(9);
    const av = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 5),
      medarbetare: tillMedarbetare().slice(0, 2),
      from: "2026-08-03",
      dagar: 7,
      timkostnad: 270,
      regler: { ...reglerFranVillkor(), minRestDaysInFourWeeks: 0 },
    });
    expect((av.payload.rules as { minRestDaysInFourWeeks: number }).minRestDaysInFourWeeks).toBe(9);
    expect(av.varningar.some((v) => /F-01/.test(v))).toBe(true);
  });

  it("skickar natt och jour upp till 27 dagar som boundary", () => {
    const personer = tillMedarbetare().slice(0, 2);
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 5),
      medarbetare: personer,
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
      regler: reglerFranVillkor(),
      schemaPass: [
        { namn: personer[0]!.namn, datum: "2026-08-11", start: "21:00", slut: "07:30" },
        { namn: personer[0]!.namn, datum: "2026-08-12", start: "23:00", slut: "06:30", jour: true },
      ],
    });
    const b = (r.payload.boundaryShifts as { date: string; type: string }[]) || [];
    expect(b.some((s) => s.date === "2026-08-11" && s.type === "night")).toBe(true);
    expect(b.some((s) => s.date === "2026-08-12" && s.type === "jour")).toBe(true);
    expect(r.payload.boundaryKnownFrom).toBe("2026-08-11");
    expect(String(r.payload.boundaryKnownTo) >= "2026-09-13").toBe(true);
  });

  it("default är optimizeExisting och generateFromNeeds kräver inte standardmallar", () => {
    const vanligt = payload(7);
    expect(vanligt.payload.planningMode).toBe("optimizeExisting");
    expect(((vanligt.payload.templates as unknown[]) || []).length).toBeGreaterThan(0);
    const generera = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 8),
      medarbetare: tillMedarbetare().slice(0, 3),
      from: "2026-08-03",
      dagar: 7,
      timkostnad: 270,
      regler: reglerFranVillkor(),
      planningMode: "generateFromNeeds",
    });
    expect(generera.payload.planningMode).toBe("generateFromNeeds");
    expect(generera.payload.existingSchedule).toBeNull();
    expect(generera.payload.templates).toEqual([]);
    expect((generera.payload.rules as { preferredMinShiftMinutes: number }).preferredMinShiftMinutes).toBe(240);
  });
});

describe("STAFF – ingen syntetisk personal", () => {
  type Emp = { id: string; code: string; name: string; ssg: number; status: string };

  function employeesOf(dagar: number) {
    return (payload(dagar).payload.employees as Emp[]) || [];
  }

  it("STAFF-A: 5 namngivna personer ger exakt 5 i payload", () => {
    expect(tillMedarbetare().length).toBe(5);
    const employees = employeesOf(7);
    expect(employees.length).toBe(5);
    expect(employees.map((e) => e.id)).toEqual(["e1", "e2", "e3", "e4", "e5"]);
    expect(employees.map((e) => e.name)).toEqual(["Topas", "Turmalin", "Jade", "Bärnsten", "Ametist"]);
  });

  it("STAFF-B: stort kundbehov skapar inga extra personer", () => {
    const employees = employeesOf(28);
    expect(employees.length).toBe(5);
    expect(employees.some((e) => /^x\d+$/.test(e.id) || /^Extra vikarie/i.test(e.name))).toBe(false);
    expect(payload(28).varningar.some((v) => /extra vikarie/i.test(v))).toBe(false);
  });

  it("STAFF-C: otillräcklig bemanning ger inte syntetiska employees", () => {
    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: tillMedarbetare().slice(0, 1),
      from: "2026-08-03",
      dagar: 28,
      timkostnad: 270,
      regler: reglerFranVillkor(),
    });
    const employees = (r.payload.employees as Emp[]) || [];
    expect(employees.length).toBe(1);
    expect(employees[0]?.id).toBe("e1");
    expect(employees.some((e) => /^x\d+$/.test(e.id))).toBe(false);
  });

  it("STAFF-D: payload klonar inte första personen till nya resurser", () => {
    const importerade = tillMedarbetare().map((m) => m.namn);
    const employees = employeesOf(28);
    expect(employees.map((e) => e.name)).toEqual(importerade);
    expect(new Set(employees.map((e) => e.id)).size).toBe(employees.length);
  });

  it("STAFF-E: Ingen placerad blir inte Vikarie 1–6", () => {
    const employees = employeesOf(7);
    expect(employees.filter((e) => e.code.startsWith("V"))).toEqual([]);
    expect(employees.some((e) => /^Vikarie \d+$/i.test(e.name))).toBe(false);
  });
});
