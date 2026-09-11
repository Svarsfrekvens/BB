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

  it("vikarier har status active", () => {
    const employees = (payload(7).payload.employees as { code: string; status: string }[]) || [];
    const vikarier = employees.filter((e) => e.code.startsWith("V"));
    expect(vikarier.length).toBeGreaterThan(0);
    for (const v of vikarier) expect(v.status).toBe("active");
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
    expect(mallar.some((m) => m.type === "jour" && m.start === "23:00" && m.end === "06:30")).toBe(true);
    expect(r.info.regler.nightFloor).toBe(0);
    expect(r.info.regler.jourFloor).toBe(1);
    const anstallda = (r.payload.employees as { night: boolean; profiles: string[] }[]) || [];
    const jourId = mallar.find((m) => m.type === "jour")?.id;
    expect(anstallda.some((e) => e.night && jourId && e.profiles.includes(jourId))).toBe(true);
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

  it("minRestDaysInFourWeeks följer styrande villkor och kan stängas av", () => {
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
    expect((av.payload.rules as { minRestDaysInFourWeeks: number }).minRestDaysInFourWeeks).toBe(0);
  });
});
