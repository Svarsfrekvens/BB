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

  it("skickar objectiveWeights med standard 50 och 2,5", () => {
    const w = payload(7).payload.objectiveWeights as { continuitySek: number; spreadSekPerPermille: number };
    expect(w.continuitySek).toBe(50);
    expect(w.spreadSekPerPermille).toBe(2.5);
  });
});
