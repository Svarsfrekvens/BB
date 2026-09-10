/**
 * Facit-test: appens beräkningskärna mot Galaxen-filerna.
 * Talen nedan är verifierade för hand (Sekoia-summa, Medvind-pass) och får
 * bara ändras om underlaget ändras – aldrig för att "få testet grönt".
 * Kör: npx vitest run
 */
import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { nyckeltal, resurskurva, perKund, procentsatser } from "@/lib/bb/core";
import { parseSekoiaRapport } from "@/lib/bb/app";      // exponera dessa två ur app.ts/medvind.ts
import { parseMedvind } from "@/lib/bb/medvind";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

describe("Galaxen – Sekoia", () => {
  it("läser alla insatser och rätt period", () => {
    expect(sekoia.rows.length).toBe(2541);
    const d = sekoia.rows.map(r => r.datum).sort();
    expect(d[0]).toBe("2026-08-03");
    expect(d.at(-1)).toBe("2026-08-30");           // D/M-datum får inte bli 8:e i varje månad
    expect(new Set(d).size).toBe(28);
  });
  it("kundbehov och kunder", () => {
    const nt = nyckeltal(sekoia.rows);
    expect(nt.kundbehovH).toBeCloseTo(578.8, 1);
    expect(perKund(sekoia.rows).length).toBe(11);   // inkl. Gemensam Norrskenet
  });
  it("status-fördelning (Uppföljning)", () => {
    const s = (k: string) => sekoia.rows.filter(r => r.status === k).length;
    expect(s("Utförd")).toBe(2324); expect(s("Inställd")).toBe(164);
    expect(s("Flyttad")).toBe(50);  expect(s("Ej utförd")).toBe(3);
  });
});

describe("Galaxen – Medvind", () => {
  it("medarbetare, vikarier och pass", () => {
    expect(medvind.medarbetare.length).toBe(11);
    expect(medvind.medarbetare.filter(m => m.vikarie).length).toBe(6);
    expect(medvind.pass.length).toBe(143);
    expect(medvind.vakantaPass).toBe(40);
  });
  it("schematid exkl. sovande jour", () => {
    expect(medvind.timmarTot).toBeCloseTo(832.0, 1);
    expect(medvind.jourTimmarTot).toBeCloseTo(210.0, 1);
  });
  it("grad läses ur schemaraden", () => {
    expect(medvind.medarbetare.find(m => m.namn === "Topas")?.grad).toBe(70);
  });
});

describe("Galaxen – nyckeltal FÖRE", () => {
  it("kundbehov ÷ schematid är 69,6 % – det är inte KPI:n Kundnära tid", () => {
    const nt = nyckeltal(sekoia.rows);
    const rk = resurskurva(sekoia.rows, "2026-08-03", "2026-08-30");
    const p = procentsatser({ kundbehovH: nt.kundbehovH, personalbehovH: nt.personalbehovH,
      dimensionerandeH: rk.dimensionerandeDirektResursbehovH, planeradeTimmar: medvind.timmarTot });
    expect(p.kundbehovAvPlanerade.varde).toBeCloseTo(69.6, 1);
    expect(rk.dimensionerandeDirektResursbehovH).toBeCloseTo(793.8, 1);
    expect(nt.kundbehovH).toBeCloseTo(578.8, 1);
    expect(medvind.timmarTot).toBeCloseTo(832.0, 1);
  });
  it("intäkt exkluderar Gemensam", () => {
    const kunder = perKund(sekoia.rows).filter(k => !/^gemensam/i.test(k.kund)).length;
    expect(kunder * 2500 * 28).toBe(700_000);
  });
});
