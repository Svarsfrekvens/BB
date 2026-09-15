import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/sekoia";
import { parseMedvind, schemaTillDatum } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import {
  kompletteraBehorighet,
  harHärleddJour,
  jourMonsterFranSchema,
  jourNamnFranSchema,
} from "@/lib/bb/nattJour";
import type { Insats } from "@/lib/bb/typer";
import type { Medarbetare } from "@/lib/bb/vy";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));
const FROM = "2026-08-03";
const galaxenPass = schemaTillDatum(medvind, FROM, 28);

function basPerson(extra: Partial<Medarbetare> = {}): Medarbetare {
  return {
    namn: extra.namn || "Anna",
    vakant: false,
    vikarie: false,
    grad: 100,
    samordnare: false,
    delegering: null,
    jour: extra.jour ?? null,
    nattbehorig: extra.nattbehorig ?? null,
    passprofil: "blandat",
    helg: "varannan",
    tidigastStart: "06:30",
    senastSlut: "23:00",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
    villkor: [],
    ...extra,
  };
}

function rader(): Insats[] {
  return (sekoia.rows as Insats[]).filter((r) => r.datum >= FROM && r.datum <= "2026-08-09");
}

describe("natt, jour och närvaro är skilda krav", () => {
  it("A: utan verifierad vaken natt är nightFloor 0", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: [basPerson()],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
    });
    expect(r.info.regler.nightFloor).toBe(0);
  });

  it("B: explicit vaken natt ger nightFloor 1", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: [basPerson({ nattbehorig: true })],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      regler: { nightFloor: 1 },
    });
    expect(r.info.regler.nightFloor).toBe(1);
    const e = (r.payload.employees as { night: boolean; jour: boolean }[])[0];
    expect(e?.night).toBe(true);
    expect(e?.jour).toBe(false);
  });

  it("C: faktiskt Jo-pass ger jour=true men night=false", () => {
    const turmalin = (medvind?.medarbetare || []).find((m) => m.namn === "Turmalin");
    expect(turmalin).toBeTruthy();
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: [basPerson({ namn: "Turmalin", grad: turmalin!.grad, jour: null, nattbehorig: null })],
      from: FROM,
      dagar: 28,
      timkostnad: 270,
      schemaPass: galaxenPass,
    });
    const e = (r.payload.employees as { name: string; night: boolean; jour: boolean }[]).find((x) => x.name === "Turmalin");
    expect(e?.jour).toBe(true);
    expect(e?.night).toBe(false);
    expect(harHärleddJour(null, "Turmalin", jourNamnFranSchema(galaxenPass))).toBe(true);
  });

  it("D: jour=true ändrar inte nattbehörighet", () => {
    const efter = kompletteraBehorighet("jour", true, { nattbehorig: null, jour: null });
    expect(efter.jour).toBe(true);
    expect(efter.nattbehorig).toBeNull();
    const nattAv = kompletteraBehorighet("nattbehorig", false, { nattbehorig: true, jour: true });
    expect(nattAv.nattbehorig).toBe(false);
    expect(nattAv.jour).toBe(true);
  });

  it("E: Galaxens Jo ger jourmall 23:00–06:30", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: (medvind?.medarbetare || []).map((m) =>
        basPerson({ namn: m.namn, grad: m.grad, vakant: m.vakant, vikarie: m.vikarie, jour: null, nattbehorig: null }),
      ),
      from: FROM,
      dagar: 28,
      timkostnad: 270,
      schemaPass: galaxenPass,
    });
    const mallar = (r.payload.templates as { type: string; start: string; end: string }[]) || [];
    expect(mallar.some((m) => m.type === "jour" && m.start === "23:00" && m.end === "06:30")).toBe(true);
    expect(mallar.filter((m) => m.type === "jour").every((m) => m.type === "jour")).toBe(true);
    expect(r.payload.rules).toMatchObject({ jour: { start: "23:00", end: "06:30" } });
  });

  it("F: jourFloor 1 med jourbehörig och jourmall", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: (medvind?.medarbetare || []).map((m) =>
        basPerson({ namn: m.namn, grad: m.grad, vakant: m.vakant, vikarie: m.vikarie, jour: null, nattbehorig: null }),
      ),
      from: FROM,
      dagar: 28,
      timkostnad: 270,
      schemaPass: galaxenPass,
    });
    expect(r.info.regler.jourFloor).toBe(1);
    const employees = r.payload.employees as { jour: boolean; night: boolean; profiles: string[] }[];
    expect(employees.some((e) => e.jour)).toBe(true);
    const jourIds = ((r.payload.templates as { id: string; type: string }[]) || []).filter((t) => t.type === "jour").map((t) => t.id);
    expect(jourIds.length).toBeGreaterThan(0);
    expect(employees.filter((e) => e.jour).every((e) => e.profiles.some((id) => jourIds.includes(id)))).toBe(true);
  });

  it("G: jour uppfyller inte nightFloor 1", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: [basPerson({ namn: "Turmalin", jour: true, nattbehorig: false })],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      schemaPass: galaxenPass.filter((p) => p.namn === "Turmalin"),
      regler: { nightFloor: 1, jourFloor: 1 },
    });
    expect(r.info.regler.nightFloor).toBe(1);
    const e = (r.payload.employees as { night: boolean; jour: boolean }[])[0];
    expect(e?.jour).toBe(true);
    expect(e?.night).toBe(false);
    expect(r.varningar.some((v) => /nattbehörig|vaken natt/i.test(v))).toBe(true);
  });

  it("H: utan Jo-schema är jourFloor 0", () => {
    const r = byggMotorPayload({
      rader: rader(),
      medarbetare: [basPerson({ jour: false })],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      schemaPass: [{ namn: "Anna", datum: FROM, start: "09:30", slut: "18:30", jour: false }],
    });
    expect(r.info.regler.jourFloor).toBe(0);
    expect(jourMonsterFranSchema([], FROM, 7).jourFloor).toBe(0);
  });
});
