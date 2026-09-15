import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/app";
import { parseMedvind, schemaTillDatum } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));
const FROM = "2026-08-03";

function person(extra: Partial<Medarbetare> = {}): Medarbetare {
  return {
    namn: extra.namn || "Anna",
    vakant: extra.vakant ?? false,
    vikarie: extra.vikarie ?? false,
    grad: extra.grad ?? 80,
    samordnare: false,
    delegering: extra.delegering ?? true,
    jour: extra.jour ?? true,
    nattbehorig: extra.nattbehorig ?? true,
    passprofil: extra.passprofil ?? "blandat",
    helg: extra.helg ?? "varannan",
    tidigastStart: "06:30",
    senastSlut: "23:00",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
    resourceType: extra.resourceType,
  };
}

function galaxenPayload(dagar = 28) {
  const schemaPass = schemaTillDatum(medvind, FROM, dagar);
  return byggMotorPayload({
    rader: sekoia.rows as Insats[],
    medarbetare: (medvind?.medarbetare || []).map((m) =>
      person({ namn: m.namn, grad: m.grad, vakant: m.vakant, vikarie: m.vikarie, delegering: true }),
    ),
    from: FROM,
    dagar,
    timkostnad: 270,
    schemaPass,
  });
}

describe("VAC – skilj medarbetare från vakanta pass", () => {
  it("VAC-A: 5 namngivna + 6 Ingen placerad → employees.length == 5", () => {
    const r = galaxenPayload(7);
    const employees = (r.payload.employees as { name: string }[]) || [];
    expect(employees.length).toBe(5);
    expect(employees.map((e) => e.name)).toEqual(["Topas", "Turmalin", "Jade", "Bärnsten", "Ametist"]);
  });

  it("VAC-B: fyra obemannade rader med pass → exakt 40 open shifts", () => {
    const open = (medvind?.pass || []).filter((p) => p.vakant);
    expect(open.length).toBe(40);
    expect(open.filter((p) => !p.jour).reduce((s, p) => s + p.timmar, 0)).toBeCloseTo(221, 0);
    expect(open.filter((p) => p.jour).reduce((s, p) => s + p.timmar, 0)).toBeCloseTo(60, 0);
    const rader = [...new Set(open.map((p) => p.rad))];
    expect(rader.length).toBe(4);
    const r = galaxenPayload(28);
    expect(((r.payload.vacantShifts as unknown[]) || []).length).toBe(40);
    expect(r.info.openShifts).toBe(40);
  });

  it("VAC-C: två tomma rader → 0 employees och 0 open shifts från dem", () => {
    const bok = XLSX.utils.book_new();
    const grid = [
      ["Schemarad", "Avtalsområde", "Placerad", "Övrigt", "Mån"],
      ["", "", "", "", "3/8"],
      ["1, Topas 70%", "", "Topas", "", "07:00-16:00  Ar"],
      ["10,", "", "Ingen placerad", "", ""],
      ["0,", "", "Ingen placerad", "", ""],
    ];
    XLSX.utils.book_append_sheet(bok, XLSX.utils.aoa_to_sheet(grid), "Medvind");
    const sk = parseMedvind(bok)!;
    expect(sk.medarbetare.map((m) => m.namn)).toEqual(["Topas"]);
    expect(sk.pass.filter((p) => /^(10,|0,)/.test(p.rad))).toEqual([]);
    expect(sk.vakantaPass).toBe(0);
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 3),
      medarbetare: sk.medarbetare.map((m) => person({ namn: m.namn, grad: m.grad, vakant: m.vakant })),
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      schemaPass: schemaTillDatum(sk, FROM, 7),
    });
    expect(((r.payload.employees as unknown[]) || []).length).toBe(1);
    expect(((r.payload.vacantShifts as unknown[]) || []).length).toBe(0);
  });

  it("VAC-D: vakant rad utan % defaultar inte till SSG 100 som person", () => {
    const bok = XLSX.utils.book_new();
    const grid = [
      ["Schemarad", "Avtalsområde", "Placerad", "Övrigt", "Mån"],
      ["", "", "", "", "3/8"],
      ["Schemarad 1", "", "Ingen placerad", "", "07:00-16:00  Ar"],
    ];
    XLSX.utils.book_append_sheet(bok, XLSX.utils.aoa_to_sheet(grid), "Medvind");
    const sk = parseMedvind(bok)!;
    expect(sk.medarbetare).toEqual([]);
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 3),
      medarbetare: [
        ...sk.medarbetare.map((m) => person({ namn: m.namn, grad: m.grad, vakant: m.vakant })),
        person({ namn: "Påhittad vakans", vakant: true, vikarie: true, grad: 100 }),
      ],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      schemaPass: schemaTillDatum(sk, FROM, 7),
    });
    const employees = (r.payload.employees as { name: string; ssg: number }[]) || [];
    expect(employees.find((e) => e.name === "Påhittad vakans")).toBeUndefined();
    expect(employees.every((e) => e.name !== "Schemarad 1")).toBe(true);
  });

  it("VAC-E: vakant rad får inte weekendMode, kundkompetens eller delegering", () => {
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 8),
      medarbetare: [
        person({ namn: "Topas", grad: 70 }),
        person({
          namn: "Vikarie 1",
          vakant: true,
          vikarie: true,
          grad: 100,
          helg: "varannan",
          delegering: true,
        }),
      ],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
    });
    const employees = (r.payload.employees as {
      name: string;
      skills: string[];
      constraints?: { hard?: { weekendMode?: string } };
    }[]) || [];
    expect(employees.map((e) => e.name)).toEqual(["Topas"]);
    expect(employees.some((e) => e.name === "Vikarie 1")).toBe(false);
  });

  it("VAC-F: open shifts räknas inte som solverkapacitet i payload", () => {
    const r = galaxenPayload(7);
    const employees = (r.payload.employees as { id: string; ssg: number }[]) || [];
    const open = (r.payload.vacantShifts as { id: string }[]) || [];
    expect(employees.length).toBe(5);
    expect(open.length).toBeGreaterThan(0);
    expect(employees.some((e) => /^open/.test(e.id))).toBe(false);
    expect(r.info.syntheticEmployees).toBe(0);
    expect(employees.reduce((s, e) => s + e.ssg, 0)).toBeLessThan(6 * 100);
  });

  it("VAC-G: explicit namngiven vikarie kan vara employee", () => {
    const r = byggMotorPayload({
      rader: (sekoia.rows as Insats[]).slice(0, 8),
      medarbetare: [
        person({ namn: "Topas", grad: 70 }),
        person({ namn: "Lisa", vikarie: true, vakant: false, grad: 100 }),
      ],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
    });
    const employees = (r.payload.employees as { name: string; code: string; resourceType: string }[]) || [];
    expect(employees.map((e) => e.name)).toEqual(["Topas", "Lisa"]);
    expect(employees.find((e) => e.name === "Lisa")?.code).toMatch(/^V/);
    expect(employees.every((e) => e.resourceType === "employee")).toBe(true);
  });
});
