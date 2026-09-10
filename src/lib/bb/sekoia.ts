// @ts-nocheck
/* Sekoia-rapportens läsare, utbruten ur app.ts så den kan testas separat.
   Ingen beräkning ändras – samma kod som tidigare låg inne i app.ts. */
import * as XLSX from "xlsx";
import * as C from "./core";

function isDate(v) { return v && typeof v === "object" && typeof v.getFullYear === "function" && !isNaN(v.getTime && v.getTime()); }

function pad2(n) { return String(n).padStart(2, "0"); }
function ar4(y) { const n = Number(y); return n < 100 ? 2000 + n : n; }

function iso(ar, manad, dag) {
  return `${ar}-${pad2(manad)}-${pad2(dag)}`;
}

/** Excel kan ha lagrat D/M som M/D i serienumret. Dagar 1–12 vänds tillbaka. */
function excelYmd(ar, manad, dag) {
  return dag <= 12 ? iso(ar, dag, manad) : iso(ar, manad, dag);
}

/** Datum ur Excel som visad text, dag/månad/år. Aldrig SheetJS .v med omkastad månad. */
export function parseDatum(v) {
  if (v == null || v === "") return "";
  if (isDate(v)) {
    return excelYmd(v.getFullYear(), v.getMonth() + 1, v.getDate());
  }
  if (typeof v === "number" && Number.isFinite(v)) {
    const hela = Math.floor(v);
    const utc = Date.UTC(1970, 0, 1) + (hela - 25569) * 86400000;
    const d = new Date(utc);
    if (Number.isNaN(d.getTime())) return "";
    return excelYmd(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
  }
  const s = String(v ?? "").trim();
  let m = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})/);
  if (m) return iso(ar4(m[3]), Number(m[2]), Number(m[1]));
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}

/** Klockslag ur samma cell som datumet, eller ur en tidscell. */
export function cellToClock(v) {
  if (isDate(v)) return `${pad2(v.getHours())}:${pad2(v.getMinutes())}`;
  if (typeof v === "number" && Number.isFinite(v)) {
    const t = ((Math.round((v % 1) * 1440) % 1440) + 1440) % 1440;
    return `${pad2(Math.floor(t / 60))}:${pad2(t % 60)}`;
  }
  const m = String(v ?? "").match(/(\d{1,2}):(\d{2})/);
  return m ? `${pad2(m[1])}:${m[2]}` : "";
}
function normRad(row) {
  return Array.from(row || [], (x) => String(x ?? "").trim().toLowerCase());
}

// Bygger personalens schema ur rapporten: varje insats knyts till den anställda
// som utförde den, utifrån insatsens planerade tid. Insatser i följd med mindre
// än fyra timmars glapp bildar ett pass – därför blir nattpass som går över
// midnatt ett enda pass, och en dag med både morgon- och kvällspass blir två.
// Kolumnen "Utförd kl." används bara för att visa om passet är utfört.
// Inga behov räknas om; detta visar bara vem som arbetade när.
function sekoiaIndividschema(grid, hi, ci) {
  if (ci.anstalld < 0) return null;
  const dagNr = (d) => Math.round(Date.parse(d + "T00:00:00Z") / 86400000);
  const dagStr = (n) => new Date(n * 86400000).toISOString().slice(0, 10);
  const perPerson = new Map();
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r];
    if (!row) continue;
    const namn = C.normKund(row[ci.anstalld]);
    const a = sekoiaStamp(row[ci.start]);
    const utford = ci.utford >= 0 ? sekoiaStamp(row[ci.utford]) : null;
    const minuter = Number(row[ci.min]);
    if (!namn || !a || !(Number.isFinite(minuter) && minuter > 0)) continue;
    if (!perPerson.has(namn)) perPerson.set(namn, []);
    perPerson.get(namn).push({
      abs: dagNr(a.datum) * 1440 + a.min,
      minuter: Math.round(minuter),
      faktisk: !!utford,
    });
  }

  const pass = [];
  for (const [namn, ev] of perPerson) {
    ev.sort((x, y) => x.abs - y.abs);
    let cur = null;
    for (const e of ev) {
      if (cur && e.abs - cur.till <= 240) {
        cur.till = Math.max(cur.till, e.abs + e.minuter);
        cur.insatser += 1;
        cur.arbetadMin += e.minuter;
        if (e.faktisk) cur.faktiska += 1;
      } else {
        cur = { namn, fran: e.abs, till: e.abs + e.minuter, insatser: 1, arbetadMin: e.minuter, faktiska: e.faktisk ? 1 : 0 };
        pass.push(cur);
      }
    }
  }
  if (!pass.length) return null;
  const columns = ["Medarbetare", "Datum", "Start", "Slut", "Betald tid h", "Slot", "Status", "Insatser", "Arbetad tid h"];
  const rows = pass
    .sort((a, b) => a.fran - b.fran || a.namn.localeCompare(b.namn, "sv"))
    .map((p) => {
      const startMin = ((p.fran % 1440) + 1440) % 1440;
      return {
        Medarbetare: p.namn,
        Datum: dagStr(Math.floor(p.fran / 1440)),
        Start: minToClock(p.fran),
        Slut: minToClock(p.till),
        "Betald tid h": Math.round(((p.till - p.fran) / 60) * 100) / 100,
        Slot: startMin >= 20 * 60 || startMin < 6 * 60 ? "Natt" : startMin < 12 * 60 ? "Dag" : "Kväll",
        Status: p.faktiska > 0 ? "Utfört" : "Planerat",
        Insatser: p.insatser,
        "Arbetad tid h": Math.round((p.arbetadMin / 60) * 100) / 100,
      };
    });
  return { columns, rows };
}



/* ---------- Rå Sekoia-export (bladet "Rapport") ---------- */
// Kolumner: Status | Intervallstart | Intervall änden | Förväntad genomförandetid (min)
// | Titel | ... | Boende | ... | För två personer | ...
// Insatsens tidsfönster = Intervallstart → Intervall änden. Är fönstret längre
// än den förväntade genomförandetiden räknas insatsen som flyttbar.
function sekoiaStamp(v) {
  const datum = parseDatum(v);
  if (!datum) return null;
  const klocka = cellToClock(v);
  const delar = klocka.split(":").map(Number);
  const min = (delar[0] || 0) * 60 + (delar[1] || 0);
  return { datum, min };
}
function minToClock(t) {
  const v = ((t % 1440) + 1440) % 1440;
  return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
}
export function parseSekoiaRapport(wb) {
  for (const name of wb.SheetNames) {
    const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: false });
    const hi = grid.findIndex((row) => {
      const c = normRad(row);
      return c.includes("intervallstart") && c.some((v) => v.startsWith("boende")) && c.includes("titel");
    });
    if (hi < 0) continue;
    const header = normRad(grid[hi]);
    const find = (fn) => header.findIndex(fn);
    const ci = {
      status: header.indexOf("status"),
      start: header.indexOf("intervallstart"),
      slutFonster: find((v) => v.startsWith("intervall ")),
      min: find((v) => v.startsWith("förväntad genomförande")),
      titel: header.indexOf("titel"),
      kund: find((v) => v === "boende"),
      tva: find((v) => v.startsWith("för två personer")),
      anstalld: header.indexOf("anställd"),
      utford: find((v) => v.startsWith("utförd kl")),


    };
    if (ci.start < 0 || ci.min < 0 || ci.kund < 0) continue;
    const rows = [];
    for (let r = hi + 1; r < grid.length; r++) {
      const row = grid[r];
      if (!row || row.every((x) => x == null || String(x).trim() === "")) continue;
      const a = sekoiaStamp(row[ci.start]);
      const minuter = Number(row[ci.min]);
      if (!a || !(Number.isFinite(minuter) && minuter > 0)) continue;
      const b = ci.slutFonster >= 0 ? sekoiaStamp(row[ci.slutFonster]) : null;
      let fonsterSlut = null;
      if (b) {
        let langd = b.min - a.min;
        if (langd < 0) langd += 1440;
        if (langd > minuter + 0.5) fonsterSlut = minToClock(b.min);
      }
      const tva = String(row[ci.tva] ?? "").trim().toLowerCase();
      rows.push({
        kallrad: r + 1,
        datum: a.datum,
        kund: C.normKund(row[ci.kund]),
        insats: C.normKund(ci.titel >= 0 ? row[ci.titel] : ""),
        start: minToClock(a.min),
        slut: minToClock(a.min + Math.round(minuter)),
        fonsterSlut,
        minuter,
        tvaPersoner: tva === "true" || tva === "ja" || tva === "1",
        flyttbar: fonsterSlut != null,
        status: C.normKund(ci.status >= 0 ? row[ci.status] : ""),
        // "Utförd kl." används bara i Uppföljning: avvikelse mot intervallstart.
        utfordMin: (() => { const u = ci.utford >= 0 ? sekoiaStamp(row[ci.utford]) : null; return u ? u.min : null; })(),
        planeradMin: a.min,
      });
    }
    if (rows.length) {
      const individschema = sekoiaIndividschema(grid, hi, ci);
      return { sheet: name, headerRow: hi + 1, rows, sekoiaIndividschema: individschema };
    }

  }
  return null;
}
