import * as XLSX from "xlsx";
import { readFileSync, writeFileSync } from "fs";
import { parseSekoiaRapport } from "../src/lib/bb/app";
import { parseMedvind } from "../src/lib/bb/medvind";
import { byggMotorPayload } from "../src/lib/bb/motorPayload";
import { STYRANDE_VILLKOR } from "../src/lib/bb/modell";
import type { Medarbetare } from "../src/lib/bb/vy";
import type { Insats } from "../src/lib/bb/typer";

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

const r = byggMotorPayload({
  rader: sekoia.rows as Insats[],
  medarbetare: (medvind?.medarbetare || []).map(
    (m): Medarbetare => ({
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
    }),
  ),
  from: "2026-08-03",
  dagar: 7,
  timkostnad: 270,
  regler: {
    maxShiftHours: villkorTal("Långpass – röd varning", 12),
    maxConsecutiveDays: Math.round(villkorTal("Max arbetsdagar i följd", 5)),
  },
  objectiveWeights: { continuitySek: 50, spreadSekPerPermille: 2.5 },
});

writeFileSync("motor/tests/galaxen_7d.json", JSON.stringify(r.payload));
console.log("skrev motor/tests/galaxen_7d.json", r.info);
