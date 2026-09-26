import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/sekoia";
import { parseMedvind } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { standardKatalog } from "@/lib/bb/aktiviteter";
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
    samordnare: extra.samordnare ?? false,
    delegering: extra.delegering ?? true,
    jour: extra.jour ?? false,
    nattbehorig: extra.nattbehorig ?? true,
    passprofil: extra.passprofil ?? "blandat",
    helg: extra.helg ?? "varannan",
    tidigastStart: extra.tidigastStart ?? "06:30",
    senastSlut: extra.senastSlut ?? "23:00",
    maxDagarIFoljd: extra.maxDagarIFoljd ?? 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
    villkor: extra.villkor,
    kompetenser: extra.kompetenser,
    workTimeModelId: extra.workTimeModelId,
  };
}

function strängvärden(v: unknown, ut: string[] = []): string[] {
  if (typeof v === "string") {
    ut.push(v);
    return ut;
  }
  if (Array.isArray(v)) {
    for (const x of v) strängvärden(x, ut);
    return ut;
  }
  if (v && typeof v === "object") {
    for (const x of Object.values(v as Record<string, unknown>)) strängvärden(x, ut);
  }
  return ut;
}

describe("dataminimering i motorpayload", () => {
  it("rå Sekoia: inga kundnamn, Medvind-namn eller Titel i utgående payload", () => {
    const rader = sekoia!.rows as Insats[];
    const kunder = [...new Set(rader.map((r) => String(r.kund || "").trim()).filter((k) => k && !/^Kund \d+$/i.test(k)))];
    const titlar = [...new Set(rader.map((r) => String(r.insats || "").trim()).filter((t) => t && !/^Insats \d+$/i.test(t)))];
    const namn = (medvind?.medarbetare || []).map((m) => m.namn).filter(Boolean);
    expect(kunder).toContain("Gemensam Norrskenet");
    expect(titlar.length).toBeGreaterThan(3);
    expect(namn).toEqual(["Topas", "Turmalin", "Jade", "Bärnsten", "Ametist"]);

    const r = byggMotorPayload({
      rader,
      medarbetare: (medvind?.medarbetare || []).map((m) =>
        person({ namn: m.namn, grad: m.grad, vakant: m.vakant, vikarie: m.vikarie }),
      ),
      from: FROM,
      dagar: 7,
      timkostnad: 270,
    });

    const värden = strängvärden(r.payload);
    for (const k of kunder) expect(värden).not.toContain(k);
    for (const t of titlar) expect(värden).not.toContain(t);
    for (const n of namn) expect(värden).not.toContain(n);

    const customers = r.payload.customers as { id: string; code: string; name: string }[];
    expect(customers.every((c) => /^k\d+$/.test(c.id))).toBe(true);
    expect(customers.every((c) => c.name === c.code && /^Kund \d+$/.test(c.name))).toBe(true);

    const employees = r.payload.employees as { id: string; code: string; name: string }[];
    expect(employees.map((e) => e.id)).toEqual(["e1", "e2", "e3", "e4", "e5"]);
    expect(employees.map((e) => e.name)).toEqual([
      "Medarbetare 1",
      "Medarbetare 2",
      "Medarbetare 3",
      "Medarbetare 4",
      "Medarbetare 5",
    ]);
    expect(employees.every((e) => /^M\d+$/.test(e.code))).toBe(true);

    const interventions = r.payload.interventions as { id: string; name: string }[];
    expect(interventions.length).toBeGreaterThan(0);
    interventions.forEach((insats, i) => {
      expect(insats.id).toBe(`i${i + 1}`);
      expect(insats.name).toBe(`Insats ${i + 1}`);
    });

    expect(r.medarbetarKarta.e1?.namn).toBe("Topas");
    const förstaKartad = Object.values(r.insatsKarta)[0];
    expect(kunder).toContain(förstaKartad?.kund);
  });

  it("bearbetad rapport Datum/Kund/Insats: samma neutralisering, oförändrade id/tider/krav", () => {
    const rader = [
      {
        id: "rad-a",
        datum: "2026-08-03",
        kund: "Karin Berg",
        insats: "Morgonhygien enligt Sekoia-Titel",
        start: "09:00",
        slut: "09:30",
        minuter: 30,
        tvaPersoner: true,
        flyttbar: false,
        status: "Utförd",
        kallrad: 2,
      },
      {
        id: "rad-b",
        datum: "2026-08-03",
        kund: "Karin Berg",
        insats: "Kvällsmedicin",
        start: "19:00",
        slut: "19:20",
        minuter: 20,
        tvaPersoner: false,
        flyttbar: false,
        status: "Utförd",
        kallrad: 3,
      },
    ] as Insats[];

    const r = byggMotorPayload({
      rader,
      medarbetare: [
        person({
          namn: "Lisa Medvind",
          grad: 70,
          delegering: true,
          kompetenser: ["undersköterska", "sårvård"],
          villkor: [
            {
              id: "k",
              typ: "kundforbud",
              styrka: "maste",
              from: "2026-08-03",
              till: "2026-08-09",
              aktiv: true,
              payload: { kund: "Karin Berg" },
            },
          ],
        }),
        person({ namn: "Erik Medvind", grad: 100, nattbehorig: true, jour: true }),
      ],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
    });

    const värden = strängvärden(r.payload);
    expect(värden).not.toContain("Karin Berg");
    expect(värden).not.toContain("Morgonhygien enligt Sekoia-Titel");
    expect(värden).not.toContain("Kvällsmedicin");
    expect(värden).not.toContain("Lisa Medvind");
    expect(värden).not.toContain("Erik Medvind");

    const customers = r.payload.customers as { id: string; code: string; name: string }[];
    expect(customers).toEqual([{ id: "k1", code: "Kund 1", name: "Kund 1", active: true }]);

    const employees = r.payload.employees as {
      id: string;
      code: string;
      name: string;
      ssg: number;
      night: boolean;
      jour: boolean;
      skills: string[];
      constraints: { hard: { weekendMode?: string } };
    }[];
    expect(employees.map((e) => e.id)).toEqual(["e1", "e2"]);
    expect(employees.map((e) => e.name)).toEqual(["Medarbetare 1", "Medarbetare 2"]);
    expect(employees[0]?.ssg).toBe(70);
    expect(employees[1]?.ssg).toBe(100);
    expect(employees[0]?.skills).toContain("undersköterska");
    expect(employees[0]?.skills).toContain("delegering");
    expect(employees[0]?.skills).toContain("kompetens:1");
    expect(employees[0]?.skills).not.toContain("sårvård");
    expect(employees[0]?.skills).not.toContain("kund:k1");
    expect(employees[1]?.skills).toContain("kund:k1");
    expect(employees[1]?.night).toBe(true);
    expect(employees[1]?.jour).toBe(true);
    expect(employees.every((e) => e.constraints.hard.weekendMode === "every_other")).toBe(true);

    const interventions = r.payload.interventions as {
      id: string;
      customerId: string;
      name: string;
      type: string;
      minutes: number;
      doubleStaff: boolean;
      weekdays: number[];
      skills: string[];
      date: string;
      start: string;
      latestEnd: string;
    }[];
    expect(interventions.map((i) => i.id)).toEqual(["i1", "i2"]);
    expect(interventions.map((i) => i.name)).toEqual(["Insats 1", "Insats 2"]);
    expect(interventions.every((i) => i.customerId === "k1")).toBe(true);
    expect(interventions[0]).toMatchObject({
      minutes: 30,
      doubleStaff: true,
      date: "2026-08-03",
      start: "09:00",
      latestEnd: "09:30",
      type: "fixed",
      weekdays: [1],
    });
    expect(interventions[1]).toMatchObject({
      minutes: 20,
      doubleStaff: false,
      date: "2026-08-03",
      start: "19:00",
      latestEnd: "19:20",
    });
    expect(interventions[0]?.skills).toContain("kund:k1");
  });

  it("pseudonymiserar okända skills men bevarar matchning inom samma payload", () => {
    const r = byggMotorPayload({
      rader: [
        {
          id: "rad-a",
          datum: "2026-08-03",
          kund: "Karin Berg",
          insats: "Morgonhygien",
          start: "09:00",
          slut: "09:30",
          minuter: 30,
          tvaPersoner: false,
          flyttbar: false,
          status: "Utförd",
          kallrad: 2,
          yrkesgrupp: "sårvård",
        },
        {
          id: "rad-b",
          datum: "2026-08-03",
          kund: "Karin Berg",
          insats: "Kväll",
          start: "19:00",
          slut: "19:20",
          minuter: 20,
          tvaPersoner: false,
          flyttbar: false,
          status: "Utförd",
          kallrad: 3,
          yrkesgrupp: "nattillsyn",
        },
      ] as Insats[],
      medarbetare: [
        person({
          namn: "Erik Medvind",
          grad: 100,
          delegering: true,
          samordnare: true,
          kompetenser: ["undersköterska", "sårvård", "nattillsyn", "sjuksköterska", "Lisa Andersson"],
          villkor: [
            {
              id: "sk1",
              typ: "kompetens",
              styrka: "maste",
              from: "2026-08-03",
              till: "2026-08-09",
              aktiv: true,
              payload: { skill: "sårvård" },
            },
            {
              id: "sk2",
              typ: "delegering",
              styrka: "maste",
              from: "2026-08-03",
              till: "2026-08-09",
              aktiv: true,
              payload: { skill: "delegering" },
            },
          ],
        }),
      ],
      from: FROM,
      dagar: 7,
      timkostnad: 270,
      planAktiviteter: standardKatalog().map((x) =>
        x.id === "veckoavstamning" ? { ...x, aktiv: true, tidstyp: "separat_tid" as const } : x,
      ),
      kontaktpersoner: { "Karin Berg": "Erik Medvind" },
    });

    const emp = (r.payload.employees as {
      skills: string[];
      skillWindows: { skill: string }[];
    })[0]!;
    expect(emp.skills).toEqual(
      expect.arrayContaining(["undersköterska", "delegering", "samordnare", "sjuksköterska", "kund:k1"]),
    );
    const sar = emp.skills.find((s) => s.startsWith("kompetens:"));
    expect(sar).toMatch(/^kompetens:\d+$/);
    expect(emp.skills).toContain("kompetens:1");
    expect(emp.skills).toContain("kompetens:2");
    expect(new Set(emp.skills.filter((s) => /^kompetens:\d+$/.test(s))).size).toBeGreaterThanOrEqual(3);
    expect(emp.skills).not.toContain("sårvård");
    expect(emp.skills).not.toContain("nattillsyn");
    expect(emp.skills).not.toContain("lisaandersson");
    expect(emp.skillWindows.map((w) => w.skill).sort()).toEqual(["delegering", "kompetens:1"].sort());

    const interventions = r.payload.interventions as {
      skills: string[];
      requiredEmployeeId?: string;
      start: string;
    }[];
    const morgon = interventions.find((i) => i.start === "09:00" && !i.requiredEmployeeId);
    const kvall = interventions.find((i) => i.start === "19:00" && !i.requiredEmployeeId);
    expect(morgon?.skills).toContain("kund:k1");
    expect(kvall?.skills).toContain("kund:k1");
    expect(morgon?.skills).toContain("kompetens:1");
    expect(kvall?.skills).toContain("kompetens:2");
    expect(morgon?.skills).not.toEqual(kvall?.skills);
    expect(emp.skills).toContain("kompetens:1");
    expect(emp.skills).toContain("kompetens:2");
    expect(interventions.some((i) => i.requiredEmployeeId === "e1")).toBe(true);

    const blob = JSON.stringify(r.payload);
    expect(blob).not.toMatch(/sårvård|nattillsyn|Lisa Andersson|Erik Medvind|Karin Berg/i);
    expect(blob).not.toContain("kompetensKarta");
  });
});
