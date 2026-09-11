/**
 * Kedjan Sekoia + Medvind + skapa (samma steg som api.skapa / skapaBalans):
 * kundbehov oförändrat, schematid EFTER densamma i Före & efter, Bemanning och Ekonomi.
 */
import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/app";
import { parseMedvind, mandagen, schemaTillDatum } from "@/lib/bb/medvind";
import { nyckeltal, filtreraPeriod, ekonomi } from "@/lib/bb/core";
import {
  analysera,
  bemanningPerSlot,
  optimeraInsatser,
  optimeraSchema,
  provaVikariepass,
  jamfor,
} from "@/lib/bb/modell";
import type { Insats } from "@/lib/bb/typer";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

function skapaKedja() {
  const from = "2026-08-03";
  const to = "2026-08-30";
  const rader = filtreraPeriod(sekoia.rows as Insats[], from, to);
  const dagLista: string[] = [];
  for (let i = 0; i < 28; i++) {
    const d = new Date(from + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + i);
    dagLista.push(d.toISOString().slice(0, 10));
  }
  const start = mandagen(from);
  const dagarTot =
    Math.round((Date.parse(to + "T12:00:00Z") - Date.parse(start + "T12:00:00Z")) / 864e5) + 1;
  const pass = schemaTillDatum(medvind, start, dagarTot).filter((p) => p.datum >= from && p.datum <= to);
  const bem = bemanningPerSlot(pass, dagLista).aktiv;
  const res = optimeraInsatser(rader, from, to, bem);
  const schemaRes = optimeraSchema({
    pass,
    rader: res.rader,
    fran: from,
    till: to,
    medarbetare: (medvind?.medarbetare || []).map((m) => ({
      namn: m.namn,
      grad: m.grad,
      vikarie: m.vikarie,
      samordnare: false,
      delegering: true,
      nattbehorig: true,
      jour: false,
      passprofil: "alla",
      helggrad: "varannan",
      tidigast: "",
      senast: "",
      maxdag: 5,
      franvaro: null,
      timkostnad: 270,
    })),
    timkostnad: 270,
  });
  const kurvaEfter = analysera({
    rader: res.rader,
    pass: schemaRes.pass,
    fran: from,
    till: to,
    timkostnad: 270,
  });
  const dim = kurvaEfter.slots.map((s) => s.dimensionerat);
  const vik = provaVikariepass(schemaRes.pass, dim, dagLista);
  const bort = new Set(vik.borttagna);
  const efterPass = schemaRes.pass.filter((p) => !bort.has(p.id));
  const bas = { fran: from, till: to, timkostnad: 270 };
  const fore = analysera({ ...bas, pass, rader });
  const efter = analysera({ ...bas, pass: efterPass, rader: res.rader });
  const fe = jamfor(fore, efter, res.flyttade, {
    h: (x) => x.toLocaleString("sv-SE", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " h",
    kr: (x) => String(x),
    pct: (x) => String(x),
  });
  const schematidEfter = efterPass.filter((p) => !p.jour).reduce((s, p) => s + p.timmar, 0);
  const oversikt = { schematidH: efter.schematidH };
  const eco = ekonomi({
    planeradeTimmar: efter.schematidH,
    timkostnad: 270,
    dimensionerandeH: efter.kundbehovH,
  });
  return { fore, efter, fe, oversikt, eco, schematidEfter, res };
}

describe("invarianter Galaxen", () => {
  const k = skapaKedja();

  it("kundbehov FÖRE === EFTER", () => {
    expect(k.efter.kundbehovH).toBeCloseTo(k.fore.kundbehovH, 5);
    expect(k.efter.kundbehovH).toBeCloseTo(nyckeltal(filtreraPeriod(sekoia.rows, "2026-08-03", "2026-08-30")).kundbehovH, 5);
  });

  it("schematid EFTER är densamma i Före & efter, Bemanning och Ekonomi", () => {
    expect(k.efter.schematidH).toBeCloseTo(k.schematidEfter, 5);
    expect(k.oversikt.schematidH).toBeCloseTo(k.efter.schematidH, 5);
    expect(k.eco.planeradeTimmar).toBeCloseTo(k.efter.schematidH, 5);
    const rad = k.fe.tabell.find((r) => r.namn === "Planerade personaltimmar");
    expect(rad).toBeTruthy();
    const efterTal = Number(String(rad!.efter).replace(/\s/g, "").replace("h", "").replace(",", "."));
    expect(efterTal).toBeCloseTo(k.efter.schematidH, 1);
  });

  it("Galaxen Före matchar känt underlag", () => {
    expect(k.fore.schematidH).toBeCloseTo(832, 1);
    expect(k.fore.kundbehovH).toBeCloseTo(578.8, 1);
    expect(k.fore.tackningPct).toBeCloseTo(82.5, 1);
  });

  it("lexikografisk lokal sökning sänker inte täckt kundbehov", () => {
    expect(k.efter.tackningPct).toBeGreaterThanOrEqual(k.fore.tackningPct - 0.05);
  });
});
