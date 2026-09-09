/* ------------------------------------------------------------------ *
 * Personalschema (Medvind-export) – inläsning.
 * Läser bladet "Medvind": en rad per schemarad, fyra veckor à sju dagar.
 * Passcell: "09:30-18:30  Ar" (flera pass per dag på egna rader i cellen).
 * Ingen beräkning av behov sker här – bara vem som arbetar när.
 * ------------------------------------------------------------------ */

import * as XLSX_STATIC from "xlsx";

export type MedvindPass = {
  id: string;
  namn: string;
  vakant: boolean;
  /** Sant när passet kommer från en obemannad schemarad (blir Vikarie N). */
  vikarie: boolean;
  vecka: number;
  dag: number; // 0 = måndag vecka 1 … 27
  start: string;
  slut: string;
  kod: string;
  jour: boolean;
  natt: boolean;
  timmar: number;
};

export type MedvindMedarbetare = {
  namn: string;
  grad: number;
  vakant: boolean;
  /** Sant för rader som saknade placerad person – hanteras som vikarie. */
  vikarie: boolean;
  rad: string;
};

export type MedvindSchema = {
  blad: string;
  filnamn: string;
  veckor: number;
  medarbetare: MedvindMedarbetare[];
  pass: MedvindPass[];
  timmarTot: number;
  jourTimmarTot: number;
  vakantaPass: number;
};


export type DatumPass = MedvindPass & { datum: string };

const KLOCKA = /(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})\s*(\S*)/;

function minuter(h: string, m: string) {
  return Number(h) * 60 + Number(m);
}
function klocka(min: number) {
  const m = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

const RAD_ALIAS = ["schemarad", "schema rad", "rad", "personal", "medarbetare", "anställd", "anstalld", "namn", "resurs"];

function harRadrubrik(rubrik: string[]) {
  return rubrik.some((h) => RAD_ALIAS.some((a) => h === a || h.startsWith(a)));
}
function antalPasscell(grid: any[][]) {
  let n = 0;
  for (const row of grid) for (const cell of row || []) if (KLOCKA.test(String(cell ?? ""))) n++;
  return n;
}

/** Läser schemabladet ur en redan öppnad arbetsbok (SheetJS). Klarar Medvind
 *  och andra exporter så länge raderna innehåller pass som "09:30-18:30". */
export function parseMedvind(wb: any, filnamn = ""): MedvindSchema | null {
  const XLSX = (globalThis as any).__BB_XLSX ?? XLSX_STATIC;
  if (!XLSX || !wb || !wb.SheetNames) return null;
  const blad: { namn: string; grid: any[][]; poang: number }[] = [];
  for (const namn of wb.SheetNames as string[]) {
    const grid: any[][] = XLSX.utils.sheet_to_json(wb.Sheets[namn], { header: 1, raw: false });
    const rubrik = Array.from(grid[0] || [], (x) => String(x ?? "").trim().toLowerCase());
    const pass = antalPasscell(grid);
    if (!pass) continue;
    blad.push({ namn, grid, poang: pass + (harRadrubrik(rubrik) ? 10000 : 0) });
  }
  blad.sort((a, b) => b.poang - a.poang);
  for (const { namn, grid } of blad) {
    const dagKol: number[] = [];
    const dagRad = Array.from(grid[1] || [], (x) => String(x ?? "").trim());
    for (let c = 4; c < Math.max(dagRad.length, 32); c++) if (dagRad[c]) dagKol.push(c);
    if (!dagKol.length) {
      // Inget datumhuvud – använd de kolumner som faktiskt innehåller pass.
      const med = new Set<number>();
      for (const row of grid) (row || []).forEach((cell, c) => { if (KLOCKA.test(String(cell ?? ""))) med.add(c); });
      [...med].sort((a, b) => a - b).forEach((c) => dagKol.push(c));
    }
    if (!dagKol.length) for (let c = 4; c < 32; c++) dagKol.push(c);


    const medarbetare: MedvindMedarbetare[] = [];
    const pass: MedvindPass[] = [];
    let timmarTot = 0;
    let jourTimmarTot = 0;
    let vakantaPass = 0;
    let vikarieNr = 0;


    const forstaDag = Math.min(...dagKol);
    for (let r = 2; r < grid.length; r++) {
      const row = grid[r];
      if (!row) continue;
      const radtext = String(row[0] ?? "").trim();
      // Namnet ligger oftast i kolumn 3, men i andra exporter i någon av de
      // första kolumnerna före passkolumnerna.
      let placerad = String(row[2] ?? "").trim();
      if (!placerad || KLOCKA.test(placerad)) {
        placerad = "";
        for (let c = 0; c < forstaDag; c++) {
          const v = String(row[c] ?? "").trim();
          if (v && !KLOCKA.test(v) && /[a-zåäöA-ZÅÄÖ]{2}/.test(v)) { placerad = v; break; }
        }
      }
      if (!radtext && !placerad) continue;
      const vakant = !placerad || /ingen placerad|vakant/i.test(placerad);
      const gradM = radtext.match(/(\d{1,3})\s*%/);
      // Obemannade rader ("Ingen placerad", "Vakant dag", "Schemarad 1") blir
      // vikarier: riktiga medarbetare i modellen, men märkta som vikarie.
      const namnRad = vakant ? `Vikarie ${vikarieNr + 1}` : placerad;


      let harPass = false;

      dagKol.forEach((c, i) => {
        const cell = String(row[c] ?? "").trim();
        if (!cell) return;
        for (const del of cell.split(/\r?\n|;/)) {
          const m = del.match(KLOCKA);
          if (!m) continue;
          const s = minuter(m[1]!, m[2]!);
          let e = minuter(m[3]!, m[4]!);
          if (e <= s) e += 1440;
          const kod = (m[5] || "Ar").trim();
          const jour = /^jo/i.test(kod);
          const timmar = (e - s) / 60;
          harPass = true;
          if (jour) jourTimmarTot += timmar;
          else timmarTot += timmar;
          if (vakant) vakantaPass += 1;
          pass.push({
            id: `p${r}-${i}-${pass.length}`,
            namn: namnRad,
            vakant,
            vikarie: vakant,
            vecka: Math.floor(i / 7),
            dag: i,
            start: klocka(s),
            slut: klocka(e),
            kod,
            jour,
            natt: s >= 22 * 60 || e > 24 * 60,
            timmar,
          });
        }
      });

      // Vakanta schemarader räknas med även utan utlagda pass: de är
      // kapacitet som kan bemannas av vikarie.
      if (harPass || !vakant || radtext) {
        if (vakant) vikarieNr += 1;
        medarbetare.push({
          namn: namnRad,
          grad: gradM ? Number(gradM[1]) : 100,
          vakant,
          vikarie: vakant,
          rad: radtext,
        });
      }
    }


    if (!pass.length) continue;
    // Skydda mot att en stor Sekoia-rapport råkar väljas som schema. Den kan
    // innehålla tider i tusentals rader, men är inte en person × dag-matris.
    if (medarbetare.length > Math.max(200, pass.length * 2)) continue;
    return {
      blad: namn,
      filnamn,
      veckor: Math.ceil(dagKol.length / 7),
      medarbetare,
      pass,
      timmarTot,
      jourTimmarTot,
      vakantaPass,
    };
  }
  return null;
}

/** Måndagen i den vecka som datumet ligger i. */
export function mandagen(iso: string) {
  const d = new Date(iso + "T12:00:00Z");
  const idx = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - idx);
  return d.toISOString().slice(0, 10);
}

function plusDagar(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Lägger schemarullen på riktiga datum. Rullen upprepas om perioden är längre. */
export function schemaTillDatum(s: MedvindSchema | null, startMandag: string, dagar: number): DatumPass[] {
  if (!s) return [];
  const cykel = Math.max(1, s.veckor * 7);
  const ut: DatumPass[] = [];
  for (let i = 0; i < dagar; i++) {
    const dagIdx = i % cykel;
    for (const p of s.pass) {
      if (p.dag !== dagIdx) continue;
      ut.push({ ...p, id: `${p.id}-${i}`, datum: plusDagar(startMandag, i) });
    }
  }
  return ut;
}
