import { describe, it, expect } from "vitest";
import { extraTillMedarbetare, tomExtraResurs, valideraExtraResurs, type ExtraResurs } from "@/lib/bb/extraResurs";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { analysera } from "@/lib/bb/modell";
import { parseSekoiaRapport } from "@/lib/bb/app";
import { parseMedvind } from "@/lib/bb/medvind";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

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
    tidigastStart: extra.tidigastStart ?? "06:30",
    senastSlut: extra.senastSlut ?? "23:00",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: extra.timkostnad ?? 270,
    anstallning: "manad",
    resourceType: extra.resourceType,
    tillgangligaDatum: extra.tillgangligaDatum,
    kompetenser: extra.kompetenser,
    maxTimmar: extra.maxTimmar,
  };
}

function galaxenPersonal(): Medarbetare[] {
  return (medvind?.medarbetare || []).map((m) =>
    person({ namn: m.namn, grad: m.grad, vakant: m.vakant, vikarie: m.vikarie }),
  );
}

function komplettExtra(delar: Partial<ExtraResurs> = {}): ExtraResurs {
  return {
    ...tomExtraResurs(),
    namn: "Extern jourresurs",
    slag: "extern",
    tillgangligaDatum: ["2026-08-14", "2026-08-15", "2026-08-16"],
    jour: true,
    timkostnad: 350,
    ...delar,
  };
}

describe("explicit extra resurs", () => {
  it("skapas inte av tom blankett eller open shifts", () => {
    const blank = tomExtraResurs();
    expect(blank.jour).toBe(false);
    expect(blank.nattbehorig).toBe(false);
    expect(blank.delegering).toBe(false);
    expect(blank.helg).toBe(false);
    expect(blank.kompetenser).toEqual([]);
    expect(blank.timkostnad).toBeNull();
    expect(valideraExtraResurs(blank).ok).toBe(false);

    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: galaxenPersonal(),
      from: "2026-08-03",
      dagar: 14,
      timkostnad: 270,
      schemaPass: [],
    });
    const employees = (r.payload.employees as { resourceType: string; name: string }[]) || [];
    expect(employees.every((e) => e.resourceType === "employee")).toBe(true);
    expect(employees.some((e) => /extern/i.test(e.name))).toBe(false);
    expect(employees).toHaveLength(5);
  });

  it("har inga automatiska defaultkompetenser", () => {
    const m = extraTillMedarbetare(komplettExtra());
    expect(m.resourceType).toBe("temporary");
    expect(m.grad).toBe(0);
    expect(m.kompetenser).toEqual([]);
    expect(m.delegering).toBe(false);
    expect(m.nattbehorig).toBe(false);
    expect(m.helg).toBe("inga");

    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: [...galaxenPersonal(), m],
      from: "2026-08-03",
      dagar: 14,
      timkostnad: 270,
    });
    const extra = (r.payload.employees as { name: string; skills: string[]; ssg: number; resourceType: string; code: string }[])
      .find((e) => e.resourceType === "temporary");
    expect(extra?.code).toMatch(/^T/);
    expect(extra?.ssg).toBe(0);
    expect(extra?.skills).toEqual([]);
    expect(extra?.skills).not.toContain("undersköterska");
  });

  it("kan begränsas till vissa datum", () => {
    const m = extraTillMedarbetare(komplettExtra({ tillgangligaDatum: ["2026-08-14"], helg: true }));
    expect(m.tillgangligaDatum).toEqual(["2026-08-14"]);
    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: [...galaxenPersonal(), m],
      from: "2026-08-03",
      dagar: 14,
      timkostnad: 270,
    });
    const extra = (r.payload.employees as { resourceType: string; constraints: { hard: { dates: string[] } } }[])
      .find((e) => e.resourceType === "temporary");
    expect(extra?.constraints.hard.dates).toEqual(["2026-08-14"]);
  });

  it("jourresurs utan jourbehörighet räknas inte som jour", () => {
    const m = extraTillMedarbetare(komplettExtra({ jour: false }));
    const r = byggMotorPayload({
      rader: sekoia.rows as Insats[],
      medarbetare: [...galaxenPersonal(), m],
      from: "2026-08-03",
      dagar: 14,
      timkostnad: 270,
    });
    const extra = (r.payload.employees as { resourceType: string; jour: boolean }[]).find((e) => e.resourceType === "temporary");
    expect(extra?.jour).toBe(false);
  });

  it("räknas i ekonomin via registrerad timkostnad inklusive jour", () => {
    const m = extraTillMedarbetare(komplettExtra({ timkostnad: 400 }));
    const lage = analysera({
      rader: [{ datum: "2026-08-08", kund: "Kund A", insats: "Stöd", start: "09:00", minuter: 30 }],
      pass: [{
        id: "j1",
        namn: m.namn,
        rad: "extra",
        vakant: false,
        vikarie: false,
        vecka: 1,
        dag: 0,
        start: "23:00",
        slut: "06:30",
        kod: "Jo",
        jour: true,
        natt: true,
        timmar: 7.5,
        datum: "2026-08-08",
      }],
      fran: "2026-08-08",
      till: "2026-08-08",
      timkostnad: 270,
      timkostnadFor: (namn) => (namn === m.namn ? 400 : 270),
      raknaJourKostnadFor: (namn) => namn === m.namn,
    });
    expect(lage.kostnad).toBeCloseTo(7.5 * 400, 5);
    expect(lage.schematidH).toBe(0);

    const utan = analysera({
      rader: [{ datum: "2026-08-08", kund: "Kund A", insats: "Stöd", start: "09:00", minuter: 30 }],
      pass: [{
        id: "j1",
        namn: "Turmalin",
        rad: "1",
        vakant: false,
        vikarie: false,
        vecka: 1,
        dag: 0,
        start: "23:00",
        slut: "06:30",
        kod: "Jo",
        jour: true,
        natt: true,
        timmar: 7.5,
        datum: "2026-08-08",
      }],
      fran: "2026-08-08",
      till: "2026-08-08",
      timkostnad: 270,
    });
    expect(utan.kostnad).toBe(0);
  });
});
