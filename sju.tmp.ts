import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import { parseSekoiaRapport } from "@/lib/bb/app";
import { parseMedvind } from "@/lib/bb/medvind";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { delaPeriod, payloadForFonster } from "@/lib/bb/motorPeriod";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = parseSekoiaRapport(wb("qa/fixtures/Galaxen_sekoia.xlsx"));
const medvind = parseMedvind(wb("qa/fixtures/Schema_galaxen.xlsx"));

const medarbetare = (medvind?.medarbetare || []).map((m: any) => ({
  namn: m.namn, vakant: m.vakant, vikarie: m.vikarie, grad: m.grad,
  samordnare: false, delegering: true, jour: false, nattbehorig: true,
  passprofil: "", helg: "varannan", tidigastStart: "", senastSlut: "",
  maxDagarIFoljd: 5, franvaro: "ingen", timkostnad: 270, anstallning: "",
})) as any;

const p = byggMotorPayload({
  rader: sekoia.rows as any,
  medarbetare,
  from: "2026-08-03",
  dagar: 7,
  timkostnad: 270,
  regler: { maxShiftHours: 12, maxConsecutiveDays: 5 },
});

const insatser = (p.payload["interventions"] as any[]) || [];
const fonster = delaPeriod(p.info.from, p.info.to, insatser);
console.log("period", p.info.from, "-", p.info.to, "fönster:", fonster.length);

const url = (process.env["OPTIMIZER_URL"] || "").replace(/\/+$/, "");
const token = process.env["OPTIMIZER_TOKEN"] || "";
let lasta: any[] = [];
for (const f of fonster) {
  const del = payloadForFonster(p.payload, f, lasta);
  const svar = await fetch(`${url}/api/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ data: del, seconds: 45 }),
  });
  const text = await svar.text();
  let d: any = null;
  try { d = JSON.parse(text); } catch { /* ignore */ }
  console.log(f.from, "-", f.to, "http", svar.status,
    "status", d?.schedule?.solverStatus,
    "pass", d?.schedule?.shifts?.length,
    "tilldelningar", d?.schedule?.assignments?.length,
    "obemannat", d?.schedule?.uncovered?.length,
    "giltigt", d?.validation?.valid);
  if (!svar.ok) console.log(text.slice(0, 300));
}
