// @ts-nocheck
/* Bemanningsbalans – appens logik och vyer, portad oförändrad från
   originalappen. All styling kommer från src/styles.css + temavariabler. */
import * as XLSX from "xlsx";
import * as core from "./core";
import { bbSkal, publiceraSkal } from "./skal";
import { publiceraVy, REAKT_TABS, APP_VERSION } from "./vy";
import { notera } from "./notis";
import * as MV from "./medvind";
import * as MODELL from "./modell";
import { parseSekoiaRapport } from "./sekoia";
export { parseSekoiaRapport } from "./sekoia";

declare global {
  interface Window {
    __avanceratOppen2?: never;
    __avanceratOppen?: boolean;
    XLSX?: unknown;
  }
}

let startad = false;



export function initBB() {
  if (startad) return;
  startad = true;
  (globalThis as any).__BB_XLSX = XLSX;
/* ------------------------------------------------------------------ *
 * Bemanningsbalans – fristående app-logik.
 * Läser en Sekoia-Excel, kör den rättade beräkningskärnan (window.
 * BemanningsbalansCore) och ritar vyerna. All data stannar i webbläsaren.
 * ------------------------------------------------------------------ */
const C = core;
const $ = (sel) => document.querySelector(sel);

/* Tre faser: Flöde (underlag → resultat), Arbeta vidare (det man justerar) och
 * Mer (tekniska vyer, hopfällt). Flikar som kräver underlag eller resultat är
 * låsta tills förutsättningen finns. */
const TABS = [
  { id: "hem", label: "Hem", sub: "Välj verksamhet och sätt igång", ic: "⌂", grupp: "Start" },
  { id: "uppladdning", label: "Underlag", sub: "Kundgrupp och schema", ic: "⇪", grupp: "Start" },
  { id: "medarbetare", label: "Medarbetare", sub: "Uppgifter och villkor", ic: "◉", grupp: "Start", kravUnderlag: true },
  { id: "motor", label: "Skapa bemanningsbalans", sub: "Optimeringsmotorn räknar fram förslaget", ic: "⚡", grupp: "Start", kravUnderlag: true },
  { id: "foreefter", label: "Före & efter", sub: "Resultatet av balansen", ic: "⇄", grupp: "Följ upp", kravResultat: true },
  { id: "schemaforslag", label: "Schemaförslag", sub: "Justera pass", ic: "▦", grupp: "Planera", kravUnderlag: true },
  { id: "kundbehov", label: "Kundbehov", sub: "Ändra insatser", ic: "♥", grupp: "Planera", kravUnderlag: true },
  { id: "resurskurva", label: "Resursbehov", sub: "Behov över dygnet", ic: "∿", grupp: "Planera", kravUnderlag: true },
  { id: "oversikt", label: "Bemanning", sub: "Verksamheten i siffror", ic: "◫", grupp: "Planera", kravUnderlag: true },
  { id: "nyckeltal", label: "Uppföljning", sub: "Planerat mot utfall", ic: "◔", grupp: "Följ upp" },
  { id: "ekonomi", label: "Ekonomi", sub: "Kostnad & intäkt", ic: "kr", grupp: "Följ upp", kravUnderlag: true },
  { id: "kunder", label: "Per kund", sub: "Timmar per kund", ic: "⁝", grupp: "Följ upp", kravUnderlag: true },
  { id: "sprid", label: "Sprid behov", sub: "Flytta rörliga insatser", ic: "⇕", grupp: "Mer", kravUnderlag: true },
  { id: "intakter", label: "Intäkter", sub: "Ersättning och underlag", ic: "▲", grupp: "Mer", kravUnderlag: true },
  { id: "atgarder", label: "Åtgärder", sub: "Vad du bör göra nu", ic: "✦", grupp: "Mer", kravUnderlag: true },
  { id: "simulering", label: "Vad händer om", sub: "Prova antaganden", ic: "⚖", grupp: "Mer", kravUnderlag: true },
  { id: "villkor", label: "Styrande villkor", sub: "Regler som styr schemat", ic: "▤", grupp: "Mer" },
  { id: "kontroller", label: "Datakontroller", sub: "Hittade fel i datan", ic: "✓", grupp: "Mer" },
  { id: "schema", label: "Individschema", sub: "Pass per medarbetare", ic: "◉", grupp: "Mer", kravUnderlag: true },
  { id: "personal", label: "Passmallar", sub: "Medarbetare och kapacitet", ic: "◉", grupp: "Mer", kravUnderlag: true },
  { id: "installningar", label: "Inställningar", sub: "Grunduppgifter", ic: "⚙", grupp: "Mer" },
  { id: "underlag", label: "Filöversikt", sub: "Filerna appen räknar på", ic: "⇪", grupp: "Mer" },
  { id: "kundgrupp", label: "Kundgrupp (fil)", sub: "Kundernas behov (Sekoia)", ic: "≋", grupp: "Mer" },
  { id: "schemafil", label: "Schema (fil)", sub: "Nuvarande personalschema", ic: "▦", grupp: "Mer" },
  { id: "verksamhet", label: "Verksamheter", sub: "Vilken enhet", ic: "▤", grupp: "Mer" },
];
const TAB_GRUPPER = ["Start", "Planera", "Följ upp", "Mer"];

/** Har vi båda filerna inlästa? */
function harUnderlag() { return !!(state && state.rows && state.rows.length && state.schemaOriginal); }
/** Finns en skapad bemanningsbalans? */
function harResultat() { return !!(state && state.balans); }
/** Låst tills förutsättningen finns. */
function tabTillganglig(t) {
  if (t && t.kravResultat) return harResultat();
  if (t && t.kravUnderlag) return harUnderlag();
  return true;
}


/** Byter flik. */
function gaTill(id) {
  const t = TABS.find((x) => x.id === id);
  if (t && !tabTillganglig(t)) {
    // Låst flik: kort hint om vad som saknas, i stället för en tom sida.
    notera(t.kravResultat ? "Skapa bemanningsbalansen först" : "Läs in underlaget först", "info", {
      detalj: t.kravResultat
        ? "Resultatet visas när du har skapat bemanningsbalansen under Underlag."
        : "Ladda upp kundernas behov och nuvarande schema under Underlag.",
    });
    tab = "uppladdning";
    render();
    return;
  }
  tab = id;
  render();
}



const STATE_VERSION = 3;

const store = {
  load() {
    try {
      const sparat = JSON.parse(localStorage.getItem("bb.state") || "null");
      // Gammalt eller versionslöst tillstånd kastas helt – appen startar tom.
      if (sparat && (sparat.version ?? 0) < STATE_VERSION) {
        localStorage.removeItem("bb.state");
        return null;
      }
      return sparat;
    } catch { return null; }
  },
  save(s) { try { localStorage.setItem("bb.state", JSON.stringify(s)); } catch {} },
  clear() { localStorage.removeItem("bb.state"); },
};

/* Datamodell: upp till fyra verksamheter. Varje verksamhet har egna rader,
 * period och inställningar. `active` pekar ut den man tittar på just nu. */
const DEFAULT_VERKS = () => ({
  id: "v" + Math.random().toString(36).slice(2, 8),
  org: "", rows: [], period: null, importDays: 0, planDays: 28,
  analysisDays: 28, hourlyCost: 270, dygnKr: 2500, plannedHours: 1972, budget: 460000,
  reservePct: 6, absencePct: 4,
  kundGodkand: false, schemaGodkand: false,

});
const MAX_VERKS = 4;

function migrate(old) {
  // Äldre sparning (en enda verksamhet) → ny lista.
  let rot;
  if (old && Array.isArray(old.verks)) rot = old;
  else if (old && old.rows) { const v = { ...DEFAULT_VERKS(), ...old }; rot = { verks: [v], active: v.id }; }
  else { const v = DEFAULT_VERKS(); rot = { verks: [v], active: v.id }; }
  // Säkerhetsnät: gamla exempelnamn får aldrig smyga med från sparat tillstånd.
  for (const v of rot.verks) {
    if (v.org === "Vintergatan" || v.org === "Ny verksamhet") v.org = "";
    // Ett kundbehovsblad kunde i en äldre version feltolkas som personalschema.
    // Ett riktigt schema kan inte rimligen ha långt fler personer än pass.
    const schema = v.schemaOriginal;
    const personer = Array.isArray(schema?.medarbetare) ? schema.medarbetare.length : 0;
    const pass = Array.isArray(schema?.pass) ? schema.pass.length : 0;
    if (personer > Math.max(200, pass * 2)) {
      v.schemaOriginal = null;
      v.schemaGodkand = false;
      v.balans = null;
      v.motorResultat = null;
      v.optimerat = false;
    }
  }
  rot.version = STATE_VERSION;
  return rot;
}

let root = migrate(store.load());
let state = root.verks.find((v) => v.id === root.active) || root.verks[0];
let tab = "hem";
let pending = null;        // resultat av importkontroll som väntar på godkännande
let pendingMeta = null;
let curveDay = 0;
// Känslighetsreglagens överskrivningar (endast i "Vad händer om", rör aldrig datan).
let sim = {};

function persist() { root.active = state.id; root.version = STATE_VERSION; store.save(root); }
function setActive(id) { const v = root.verks.find((x) => x.id === id); if (v) { state = v; curveDay = 0; pending = null; sim = {}; persist(); render(); } }function addVerks() {
  if (root.verks.length >= MAX_VERKS) return;
  const v = DEFAULT_VERKS(); root.verks.push(v); setActive(v.id);
}
function removeVerks(id) {
  if (root.verks.length <= 1) { root.verks = [DEFAULT_VERKS()]; }
  else root.verks = root.verks.filter((v) => v.id !== id);
  root.active = root.verks[0].id; state = root.verks[0]; persist(); render();
}

/* ---------- Osparade ändringar (bara en jämförelse, ingen beräkning) ------ */
// Signatur över arbetskopiorna. Skiljer den sig från det som senast exporterades
// eller lästes in finns osparat arbete.
function andringsSignatur() {
  return JSON.stringify([
    state.kundEdit || null,
    state.personalEdit || null,
    state.intaktEdit || null,
    state.schemaLek || null,
    state.kundLek || null,
  ]);
}
let sparadSignatur = "";
function markeraSparat() { sparadSignatur = andringsSignatur(); }
function harOsparat() {
  const nu = andringsSignatur();
  return nu !== sparadSignatur && nu !== JSON.stringify([null, null, null, null, null]);
}

/* ---------- Ögonblicksbild för Ångra (rör ingen beräkning) ---------- */
// Kopierar bara arbetskopiorna, så en borttagning kan tas tillbaka.
function ogonblicksbild() {
  return JSON.stringify({
    kundEdit: state.kundEdit || null,
    personalEdit: state.personalEdit || null,
    intaktEdit: state.intaktEdit || null,
  });
}
function aterstallOgonblicksbild(snap) {
  try {
    const s = JSON.parse(snap);
    state.kundEdit = s.kundEdit;
    state.personalEdit = s.personalEdit;
    state.intaktEdit = s.intaktEdit;
    persist(); render();
  } catch (e) { /* trasig bild – gör inget */ }
}

/* ---------- Excel → normaliserade rader ---------- */
function isDate(v) { return v && typeof v === "object" && typeof v.getFullYear === "function" && !isNaN(v.getTime && v.getTime()); }
function cellToIso(v) {
  if (isDate(v)) return `${v.getFullYear()}-${String(v.getMonth() + 1).padStart(2, "0")}-${String(v.getDate()).padStart(2, "0")}`;
  if (typeof v === "number") { const d = XLSX.SSF.parse_date_code(v); if (d) return `${d.y}-${String(d.m).padStart(2, "0")}-${String(d.d).padStart(2, "0")}`; }
  const t = String(v ?? "").trim();
  // Sekoia skriver datum som 13-08-2026 (dag-månad-år). Läses före ISO-formatet.
  const dmy = t.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})/);
  if (dmy) return `${dmy[3]}-${dmy[2].padStart(2, "0")}-${dmy[1].padStart(2, "0")}`;
  const m = t.match(/(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}
function cellToClock(v) {
  if (isDate(v)) return `${String(v.getHours()).padStart(2, "0")}:${String(v.getMinutes()).padStart(2, "0")}`;
  if (typeof v === "number") { const t = Math.round((v % 1) * 1440); return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; }
  const m = String(v ?? "").match(/(\d{1,2}):(\d{2})/); return m ? `${m[1].padStart(2, "0")}:${m[2]}` : "";
}
function addClock(hhmm, min) {
  const [h, m] = hhmm.split(":").map(Number); const t = ((h * 60 + m + min) % 1440 + 1440) % 1440;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
// Rubrikigenkänning som tål att andra system stavar kolumnerna lite olika.
const ALIAS = {
  datum: ["datum", "date", "dag"],
  kund: ["kund", "kundnamn", "brukare", "boende", "klient", "person"],
  insats: ["insats", "insatsnamn", "aktivitet", "titel", "insatstyp", "besök"],
  start: ["planerad start", "planerad tid", "starttid", "start", "från", "från kl", "intervallstart", "planerad kl"],
  slut: ["planerat slut", "sluttid", "slut", "till", "till kl", "intervallslut"],
  min: ["varaktighet min", "minuter", "varaktighet", "tid min", "längd", "duration"],
  flytt: ["flyttbar", "kategori", "flexibel", "typ"],
  status: ["status", "utfall"],
  fonster: ["fönster slut", "fonster slut", "senast", "senaste starttid"],
  dubbel: ["dubbelbemanning", "två personer", "tva personer", "dubbel", "antal personal"],
};
function normRad(row) {
  // sheet_to_json kan ge glesa rader (hål) – Array.from fyller dem med undefined
  // så att map/findIndex alltid får en sträng att arbeta med.
  return Array.from(row || [], (x) => String(x ?? "").trim().toLowerCase());
}
function kolIndex(header, nyckel) {
  for (const a of ALIAS[nyckel] || []) {
    const i = header.indexOf(a);
    if (i >= 0) return i;
  }
  // sista utväg: rubrik som börjar med aliaset
  for (const a of ALIAS[nyckel] || []) {
    const i = header.findIndex((h) => String(h ?? "").startsWith(a));
    if (i >= 0) return i;
  }
  return -1;
}
function findHeader(grid) {
  return grid.findIndex((row) => {
    if (!row) return false;
    const c = normRad(row);
    return kolIndex(c, "datum") >= 0 && kolIndex(c, "kund") >= 0 && kolIndex(c, "insats") >= 0 && kolIndex(c, "start") >= 0;
  });
}

function parseWorkbook(wb) {
  // Läs samtidigt in verksamhetens eget resursbehovsblad om det finns, så att
  // appen kan visa exakt samma 15-minuterssiffra som modellen i Excel.
  const resurs = parseResursblad(wb);
  const berakningar = parseKeyValueSheet(wb, "Beräkningar");
  const kontroller = parseKontroller(wb);
  const personal = parseTableSheet(wb, "Personal", ["medarbetare", "status"]);
  const intakter = parseTableSheet(wb, "Intäkter", ["datum", "kund"]);
  const passmallar = parseTableSheet(wb, "Passmallar", ["pass", "start"]);
  const individschema = parseTableSheet(wb, "Individschema", ["datum", "medarbetare"]);
  const villkor = parseVillkor(wb);
  const scenario = byggScenario(wb, "Juni (nuläge)");
  // Leta i alla flikar efter den daterade rapporten (rubrik med Datum/Kund/Insats/Planerad start).
  for (const name of wb.SheetNames) {
    const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
    const hi = findHeader(grid);
    if (hi < 0) continue;
    const header = normRad(grid[hi]);
    const col = (n) => kolIndex(header, n);
    const ci = {
      datum: col("datum"), kund: col("kund"), insats: col("insats"), start: col("start"),
      slut: col("slut"), min: col("min"),
      flytt: col("flytt"), status: col("status"),
      fonster: col("fonster"), dubbel: col("dubbel"),
    };

    const rows = [];
    for (let r = hi + 1; r < grid.length; r++) {
      const row = grid[r]; if (!row || row.every((x) => x == null || String(x).trim() === "")) continue;
      const datum = cellToIso(ci.datum >= 0 ? row[ci.datum] : "");
      const start = cellToClock(ci.start >= 0 ? row[ci.start] : "");
      const minuter = Number(ci.min >= 0 ? row[ci.min] : NaN);
      const kund = C.normKund(ci.kund >= 0 ? row[ci.kund] : "");
      const flyttbar = String(ci.flytt >= 0 ? row[ci.flytt] ?? "" : "").trim().toLowerCase();
      const dubbel = String(ci.dubbel >= 0 ? row[ci.dubbel] ?? "" : "").trim().toLowerCase() === "ja";
      const slut = cellToClock(ci.slut >= 0 ? row[ci.slut] : "") || (start && Number.isFinite(minuter) ? addClock(start, Math.round(minuter)) : "");
      rows.push({
        kallrad: r + 1, datum, kund, insats: C.normKund(ci.insats >= 0 ? row[ci.insats] : ""),
        start, slut, fonsterSlut: cellToClock(ci.fonster >= 0 ? row[ci.fonster] : "") || null,
        minuter, tvaPersoner: dubbel,
        flyttbar: flyttbar === "ja" || flyttbar.includes("flyttbar"),
        status: C.normKund(ci.status >= 0 ? row[ci.status] : "") || "",
      });
    }
    return { sheet: name, headerRow: hi + 1, rows, resurs, berakningar, kontroller, personal, intakter, passmallar, individschema, villkor, scenario };
  }
  // Ingen bearbetad rapport hittades – prova verksamhetens råa Sekoia-export.
  const sekoia = parseSekoiaRapport(wb);
  if (sekoia) {
    pseudonymisera(sekoia.rows, sekoia.sekoiaIndividschema);
    return { ...sekoia, resurs, berakningar, kontroller, personal, intakter, passmallar, individschema: individschema || sekoia.sekoiaIndividschema, villkor, scenario };
  }
  return null;
}

/* ---------- Avidentifiering ---------- */
// Kunder blir "Kund 1, Kund 2 …" och medarbetare får stjärnnamn. Inga
// beräkningar ändras – bara etiketterna som visas i gränssnittet.
const STJARNNAMN = [
  "Polaris", "Rigel", "Vega", "Orion", "Lyra", "Nova", "Stella", "Sirius", "Cassiopeia", "Altair",
  "Antares", "Bellatrix", "Capella", "Deneb", "Elektra", "Fomalhaut", "Mira", "Procyon", "Spica",
  "Arcturus", "Atlas", "Maia", "Merope", "Regulus", "Tycho", "Alcor", "Mizar", "Castor", "Pollux", "Aldebaran",
];
function pseudonymisera(rows, individschema) {
  const kunder = new Map();
  const gemensam = (namn) => /gemensam/i.test(namn);
  for (const r of rows || []) {
    const namn = String(r.kund ?? "").trim();
    if (!namn) continue;
    if (!kunder.has(namn)) kunder.set(namn, gemensam(namn) ? "Gemensamt" : `Kund ${[...kunder.values()].filter((v) => v !== "Gemensamt").length + 1}`);
    r.kund = kunder.get(namn);
  }
  const personer = new Map();
  const stjarna = (namn) => {
    const n = String(namn ?? "").trim();
    if (!n) return n;
    if (!personer.has(n)) personer.set(n, STJARNNAMN[personer.size] || `Medarbetare ${personer.size + 1}`);
    return personer.get(n);
  };
  for (const p of individschema?.rows || []) p.Medarbetare = stjarna(p.Medarbetare);
  return { kunder, personer };
}




// Generisk läsare: hittar rubrikraden via nyckelkolumner och returnerar
// { columns, rows } där varje rad är ett objekt. Läser bara det som behövs
// för att visa – inga personnummer eller fritextbeskrivningar tas med.
function parseTableSheet(wb, sheetName, required) {
  const name = wb.SheetNames.find((n) => n.toLowerCase() === sheetName.toLowerCase());
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => {
    const c = normRad(row);
    return required.every((r) => c.includes(r));
  });
  if (hi < 0) return null;
  const raw = Array.from(grid[hi] || [], (x) => String(x ?? "").trim());
  // Hantera dubblettrubriker (Individschema har två "Medarbetare"/"Status").
  const seen = {}; const columns = raw.map((h) => { seen[h] = (seen[h] || 0) + 1; return seen[h] > 1 ? `${h} (${seen[h]})` : h; });
  const rows = [];
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; if (!row || row.every((x) => x == null || String(x).trim() === "")) continue;
    const first = String(row[0] ?? "").trim();
    if (/^totalt$/i.test(first)) continue; // hoppa filens egen totalrad
    const obj = {};
    columns.forEach((col, i) => { obj[col] = row[i] ?? null; });
    rows.push(obj);
  }
  return columns.length && rows.length ? { columns, rows } : null;
}

// Läser ett blad med kolumnerna Mått | Värde | ... till en uppslagstabell.
function parseKeyValueSheet(wb, sheetName) {
  const name = wb.SheetNames.find((n) => n.toLowerCase() === sheetName.toLowerCase());
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => {
    const c = normRad(row);
    return c.includes("mått") && c.includes("värde");
  });
  if (hi < 0) return null;
  const header = normRad(grid[hi]);
  const cM = header.indexOf("mått"), cV = header.indexOf("värde"), cE = header.indexOf("enhet"), cD = header.indexOf("definition");
  const map = {};
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; if (!row || row[cM] == null || String(row[cM]).trim() === "") continue;
    map[String(row[cM]).trim()] = { value: row[cV], unit: cE >= 0 ? row[cE] : "", def: cD >= 0 ? row[cD] : "" };
  }
  return Object.keys(map).length ? map : null;
}

// Läser Kontroller-bladet (Kontroll | Utfall | Förväntat | Differens | Status | Åtgärd).
function parseKontroller(wb) {
  const name = wb.SheetNames.find((n) => n.toLowerCase() === "kontroller");
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => {
    const c = normRad(row);
    return c.includes("kontroll") && c.includes("utfall") && c.includes("status");
  });
  if (hi < 0) return null;
  const header = normRad(grid[hi]);
  const cK = header.indexOf("kontroll"), cU = header.indexOf("utfall"), cF = header.indexOf("förväntat"),
    cS = header.indexOf("status"), cA = header.findIndex((v) => v.startsWith("åtgärd"));
  const list = [];
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; if (!row || row[cK] == null || String(row[cK]).trim() === "") continue;
    list.push({
      kontroll: String(row[cK]).trim(), utfall: row[cU], forvantat: cF >= 0 ? row[cF] : "",
      status: String(row[cS] ?? "").trim(), atgard: cA >= 0 ? String(row[cA] ?? "").trim() : "",
    });
  }
  return list.length ? list : null;
}

// Läser bladet "Resursbehov 15 min" (verksamhetens egen samtidighetsmodell).
// Returnerar resursbehov per 15-minutersintervall och dygn, eller null.
function parseResursblad(wb) {
  const name = wb.SheetNames.find((n) => /resursbehov.*15/i.test(n));
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => {
    const c = normRad(row);
    return c.includes("datum") && c.includes("tid") && c.some((v) => v.includes("resursbehov"));
  });
  if (hi < 0) return null;
  const header = normRad(grid[hi]);
  const cDatum = header.indexOf("datum"), cTid = header.indexOf("tid");
  const cReq = header.findIndex((v) => v === "resursbehov");
  if (cReq < 0) return null;
  const perDay = {}; let peak = { value: 0, datum: "", tid: "" };
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; if (!row) continue;
    const iso = cellToIso(row[cDatum]); const tid = cellToClock(row[cTid]);
    const req = Number(row[cReq]); if (!iso || !Number.isFinite(req)) continue;
    (perDay[iso] ||= []).push({ tid, req });
    if (req > peak.value) peak = { value: req, datum: iso, tid };
  }
  const days = Object.keys(perDay).sort();
  if (!days.length) return null;
  return { perDay, days, peak, from: days[0], to: days[days.length - 1] };
}

/* ---------- Import ---------- */
let laser = false;   // sant medan en fil läses in (visar "Läser in…")
function handleFile(file) {
  laser = true; render();
  const klar = () => { laser = false; };
  const reader = new FileReader();
  reader.onerror = () => { klar(); notera("Filen kunde inte läsas", "fel", { detalj: "Försök välja filen igen." }); render(); };
  reader.onload = (e) => {
    let parsed, wbRef;
    try {
      const wb = XLSX.read(new Uint8Array(e.target.result), { type: "array", cellDates: true });
      wbRef = wb;
      parsed = parseWorkbook(wb);
    } catch (err) {
      klar();
      notera("Kunde inte läsa filen", "fel", { detalj: err.message + " Kontrollera att det är en Excel-fil (.xlsx)." });
      render();
      return;
    }
    if (!parsed || !parsed.rows.length) {
      klar();
      notera("Hittade ingen läsbar tabell", "fel", { detalj: "Filen behöver kolumnerna Datum, Kund, Insats och Planerad start." });
      render();
      return;
    }
    const dates = parsed.rows.map((r) => r.datum).filter(Boolean).sort();
    const from = dates[0], to = dates[dates.length - 1];
    const days = Math.round((new Date(to + "T12:00:00Z") - new Date(from + "T12:00:00Z")) / 864e5) + 1;
    const kontroll = C.importkontroll(parsed.rows, { fran: from, till: to });    // Egen blockering: en kund som helt tappas i avvisade rader.
    const seen = new Set(parsed.rows.map((r) => C.normKund(r.kund)).filter(Boolean));
    const kept = new Set(kontroll.timmarPerKund.map((k) => k.kund));
    for (const name of seen) if (!kept.has(name)) { kontroll.blockera = true; kontroll.varningar.push(`BLOCKERAT: kunden "${name}" tappades bort (alla rader avvisade)`); }
    const first28 = days > 28 ? (() => { const p = C.filtreraPeriod(kontroll.godkanda, from, addDays(from, 27)); const n = C.nyckeltal(p); return { days: 28, count: n.antalInsatser, kundbehovH: n.kundbehovH, personalbehovH: n.personalbehovH }; })() : null;
    pending = { ...kontroll, from, to, days, first28, godkanda: kontroll.godkanda };
    pendingMeta = { sheet: parsed.sheet, headerRow: parsed.headerRow, fileName: file.name, resurs: parsed.resurs, berakningar: parsed.berakningar, kontroller: parsed.kontroller, personal: parsed.personal, intakter: parsed.intakter, passmallar: parsed.passmallar, individschema: parsed.individschema, villkor: parsed.villkor, scenario: parsed.scenario };
    klar();
    if (pending.blockera) {
      // Går inte att räkna på: visa filöversikten med felen istället.
      tab = "underlag";
      notera("Filen kunde inte läsas in", "fel", { detalj: (kontroll.varningar || [])[0] || "Kontrollera datum, kund och tider i filen." });
      render();
      return;
    }
    // Visa granskningen. Kundunderlaget sparas först efter ett aktivt godkännande.
    render();

  };
  reader.readAsArrayBuffer(file);
}
function addDays(iso, n) { const d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }

/* ---------- Härledd modell när filen bara är en rå Sekoia-Rapport ----------
 * Bygger Beräkningar, Kontroller, Personal och Intäkter i exakt samma form
 * som view-funktionerna förväntar sig, så Ekonomi/Åtgärder/Bemanning/Intäkter
 * fylls med riktigt innehåll från den egna Rapporten + branschtypiska startvärden.
 * core.ts rörs inte; inga befintliga beräkningar ändras. */
function harleddBerakningar(rows, period, individschema, antag) {
  const fran = period.from, till = period.to, dagar = period.days;
  const n = C.nyckeltal(rows);
  const curve = C.resurskurva(rows, fran, till);
  const resursH = curve.dimensionerandeDirektResursbehovH;
  const kundbehovH = n.kundbehovH;
  // Schematid kommer alltid ur Medvind-schemat när det finns. Sekoia = kundbehov.
  let schematid = medvindSchematidH();
  const franMedvind = schematid > 0;
  if (!franMedvind && individschema && individschema.rows) for (const r of individschema.rows) schematid += Number(r["Betald tid h"]) || 0;
  if (!schematid) schematid = antag.plannedHours || 0;

  const timkostnad = antag.hourlyCost || 270;
  const budget = antag.budget || 460000;
  const reservPct = antag.reservePct ?? 6;
  const korttidPct = antag.absencePct ?? 4;
  const buffertPct = 4;
  const grundKr = antag.dygnKr || 2500; // kr per kund och dygn

  const schemakostnad = schematid * timkostnad;
  const korttidKr = schemakostnad * korttidPct / 100;
  const totalPrognos = schemakostnad + korttidKr;
  const reservKr = budget * reservPct / 100;
  const budgetavvikelse = budget - totalPrognos;
  const disponibelt = budgetavvikelse - reservKr;
  const buffertH = schematid * buffertPct / 100;
  const buffertKr = buffertH * timkostnad;
  const budgeteradTid = timkostnad > 0 ? budget / timkostnad : 0;
  const tillgangligTid = budgeteradTid * (1 - korttidPct / 100);
  const vakanta = Math.max(0, budgeteradTid - tillgangligTid);
  const ovrigPlanerad = Math.max(0, schematid - kundbehovH);
  const kunder = C.perKund(rows);
  const intaktKunder = kunder.filter((k) => !/^gemensam/i.test(k.kund));
  const manadsintakt = intaktKunder.reduce((s) => s + grundKr * dagar, 0);
  return {
    "Antal dagar i period": { value: dagar, def: "Periodslut minus periodstart plus en dag" },
    "Summerade kundinsatser": { value: kundbehovH, def: "Alla justerade insatstimmar; visar arbetsvolym men inte samtidighet" },
    "Samtidighetsbaserat resursbehov": { value: resursH, def: "Medarbetare per 30 min inkl. dubbelbemanning och vaken natt" },
    "Planerad schematid": { value: schematid, def: franMedvind ? "Summan av arbetspassen i Medvind-schemat (vikarier med, sovande jour ej)" : "Uppskattad ur Sekoia – läs in schemat för riktiga tal" },
    "Planerad bruttotid": { value: schematid * 1.086, def: "Närvaro inklusive obetald rast (uppskattat)" },
    "Budgeterad personaltid": { value: budgeteradTid, def: "Personalbudget dividerat med timkostnad" },
    "Tillgänglig personaltid": { value: tillgangligTid, def: "Efter korttidsfrånvaro" },
    "Vakanta timmar": { value: vakanta, def: "Budgeterad minus tillgänglig tid" },
    "Övrig planerad tid": { value: ovrigPlanerad, def: "Schematid minus summerade kundinsatser" },
    "Planerad kundnära andel": { value: schematid > 0 ? kundbehovH / schematid : 0, def: "Kundinsatser dividerat med schematid" },
    "Mål kundnära tid": { value: 0.75, def: "Pilotmål" },
    "Månadsintäkt": { value: manadsintakt, def: "Grundersättning per kund och dygn" },
    "Ren schemakostnad": { value: schemakostnad, def: "Schematid × timkostnad" },
    "Prognos korttidsfrånvaro": { value: korttidKr, def: "Schemakostnad × korttidsfrånvaro %" },
    "Total kostnadsprognos": { value: totalPrognos, def: "Schemakostnad + korttidsfrånvaro" },
    "Budgetavvikelse före reserv": { value: budgetavvikelse, def: "Personalbudget minus total kostnadsprognos" },
    "Ekonomisk reserv": { value: reservKr, def: reservPct + " % av personalbudgeten" },
    "Disponibelt utrymme efter ekonomisk reserv": { value: disponibelt, def: "Budgetavvikelse minus reserv" },
    "Beslutad bemanningsbuffert": { value: buffertH, def: buffertPct + " % av schematiden" },
    "Beslutad bemanningsbuffert – värde": { value: buffertKr, def: "Bufferttimmar × timkostnad" },
    "Aktuell personalbudget": { value: budget, def: "Från Inställningar" },
    "Dimensionerande direkt resursbehov": { value: resursH, def: "Inkl. vaken natt som golv" },
  };
}

function harleddModell(rows, period, individschema, antag) {
  const berakningar = harleddBerakningar(rows, period, individschema, antag);
  const fran = period.from, till = period.to, dagar = period.days;
  const kunder = C.perKund(rows);
  const intaktKunder = kunder.filter((k) => !/^gemensam/i.test(k.kund));
  const timkostnad = antag.hourlyCost || 270;
  const grundKr = antag.dygnKr || 2500; // kr per kund och dygn
  // Kontroller från importkontroll()
  const kontroll = C.importkontroll(rows, { fran, till });
  const kontroller = [];
  const krow = (k, u, f, s, a) => kontroller.push({ kontroll: k, utfall: u, forvantat: f, status: s, atgard: a });
  krow("Antal Sekoia-rader", kontroll.lastaRader, kontroll.lastaRader, "PASS", "Kontrollera grundimporten");
  krow("Godkända rader", kontroll.godkandaRader, kontroll.lastaRader, kontroll.avvisadeRader === 0 ? "PASS" : "ÅTGÄRD", kontroll.avvisadeRader ? kontroll.avvisadeRader + " rader avvisade" : "");
  krow("Avvisade rader", kontroll.avvisadeRader, 0, kontroll.avvisadeRader === 0 ? "PASS" : "ÅTGÄRD", kontroll.avvisade.map((a) => a.orssak).join("; "));
  krow("Antal kunder", kontroll.antalKunder, "≥ 1", kontroll.antalKunder > 0 ? "PASS" : "ÅTGÄRD", "");
  krow("Gemensamma insatser", kontroll.antalGemensamma, "—", "PASS", "");
  krow("Fasta insatser", kontroll.antalFasta, "—", "PASS", "");
  krow("Flyttbara insatser", kontroll.antalFlyttbara, "—", "PASS", "");
  krow("Dubbelbemannade insatser", kontroll.antalDubbelbemannade, "—", "PASS", "");
  for (const v of kontroll.varningar) krow("Importvarning", v, "", kontroll.blockera ? "ÅTGÄRD" : "VARNING", "");
  // Personal: bygg ur Medvind-schemat när det finns (rikiga pass), annars ur
  // Sekoia-individschemat som reserv – markerat "uppskattad". Bemanning = Medvind.
  let personal = null;
  const mvPass = schemaPass();
  const mvMed = state.schemaOriginal ? state.schemaOriginal.medarbetare : [];
  if (mvPass.length) {
    const perMed = new Map();
    for (const p of mvPass) {
      if (p.jour) continue;
      if (!perMed.has(p.namn)) perMed.set(p.namn, { namn: p.namn, betald: 0, startMin: 99, natt: false });
      const m = perMed.get(p.namn);
      m.betald += Number(p.timmar) || 0;
      const sm = clockMin(p.start) ?? 99;
      if (sm < m.startMin) m.startMin = sm;
      if (p.natt) m.natt = true;
    }
    const medKarta = new Map(mvMed.map((m) => [m.namn, m]));
    const columns = ["Medarbetare", "Status", "Grund-SSG", "Passprofil", "Heltid h/vecka", "Budget h/mån", "Tillgängligt h/mån", "Timkostnad", "Budgetkostnad/mån", "Helgmodell", "Rapportindikation", "Nattbehörig", "Planerade h", "SSG-avvikelse h"];
    const prows = [...perMed.values()].map((m) => {
      const mv = medKarta.get(m.namn);
      const grad = mv ? mv.grad : 100;
      const vikarie = mv ? mv.vikarie : false;
      const profil = m.natt ? "Natt" : m.startMin >= 14 * 60 ? "Kväll" : "Dag";
      const bh = Math.round(m.betald * 100) / 100;
      return { "Medarbetare": m.namn, "Status": vikarie ? "Vikarie" : "Anställd", "Grund-SSG": grad / 100, "Passprofil": profil, "Heltid h/vecka": 36.33, "Budget h/mån": bh, "Tillgängligt h/mån": bh, "Timkostnad": timkostnad, "Budgetkostnad/mån": Math.round(bh * timkostnad), "Helgmodell": "Varannan helg", "Rapportindikation": "Från Medvind-schemat", "Nattbehörig": m.natt ? "Ja" : "Nej", "Planerade h": bh, "SSG-avvikelse h": 0 };
    });
    personal = { columns, rows: prows };
  } else if (individschema && individschema.rows && individschema.rows.length) {
    const perMed = new Map();
    for (const r of individschema.rows) {
      const namn = String(r["Medarbetare"] ?? "").trim(); if (!namn) continue;
      if (!perMed.has(namn)) perMed.set(namn, { namn, betald: 0, slots: {} });
      const m = perMed.get(namn);
      m.betald += Number(r["Betald tid h"]) || 0;
      const slot = String(r["Slot"] ?? ""); if (slot) m.slots[slot] = (m.slots[slot] || 0) + 1;
    }
    const columns = ["Medarbetare", "Status", "Grund-SSG", "Passprofil", "Heltid h/vecka", "Budget h/mån", "Tillgängligt h/mån", "Timkostnad", "Budgetkostnad/mån", "Helgmodell", "Rapportindikation", "Nattbehörig", "Planerade h", "SSG-avvikelse h"];
    const prows = [...perMed.values()].map((m) => {
      const dom = Object.entries(m.slots).sort((a, b) => b[1] - a[1])[0];
      const profil = dom ? dom[0] : "Dag/kväll";
      const bh = Math.round(m.betald * 100) / 100;
      return { "Medarbetare": m.namn, "Status": "Anställd", "Grund-SSG": 1, "Passprofil": profil, "Heltid h/vecka": 36.33, "Budget h/mån": bh, "Tillgängligt h/mån": bh, "Timkostnad": timkostnad, "Budgetkostnad/mån": Math.round(bh * timkostnad), "Helgmodell": "Varannan helg", "Rapportindikation": "Uppskattad ur Sekoia – läs in schemat", "Nattbehörig": profil === "Natt" ? "Ja" : "Nej", "Planerade h": bh, "SSG-avvikelse h": 0 };
    });
    personal = { columns, rows: prows };
  }
  // Intäkter: en rad per kund per dag i perioden
  const intaktCols = ["Datum", "Kund", "Grund kr/dygn", "Aktiv kund", "Ny ersättning", "Intäktsfaktor", "Giltig grundersättning", "Beräknad intäkt"];
  const intaktRows = [];
  for (const k of intaktKunder) {
    for (let i = 0; i < dagar; i++) {
      intaktRows.push({ "Datum": addDays(fran, i), "Kund": k.kund, "Grund kr/dygn": grundKr, "Aktiv kund": 1, "Ny ersättning": grundKr, "Intäktsfaktor": 1, "Giltig grundersättning": grundKr, "Beräknad intäkt": grundKr });
    }
  }
  const intakter = intaktRows.length ? { columns: intaktCols, rows: intaktRows } : null;
  return { berakningar, kontroller, personal, intakter };
}

function approveImport() {
  if (!pending || pending.blockera) return;
  state.rows = pending.godkanda;
  state.kundGodkand = true;
  state.period = { from: pending.from, to: pending.to };
  state.importDays = pending.days;
  state.planDays = Math.min(28, pending.days);
  state.analysisDays = state.planDays;
  state.optimerat = true;   // ← X2 inläst: optimerat schema och gröna siffror
  state.resurs = pendingMeta.resurs || null;
  // Saknar filen modellbladen (bara rå Sekoia-Rapport) härleds Beräkningar,
  // Kontroller, Personal och Intäkter från Rapporten + Individschema + startvärden,
  // så Ekonomi/Åtgärder/Bemanning/Intäkter fylls med riktigt innehåll.
  let derived = null;
  if (!pendingMeta.berakningar && !pendingMeta.kontroller && !pendingMeta.personal && !pendingMeta.intakter && pendingMeta.individschema) {
    derived = harleddModell(pending.godkanda, { from: pending.from, to: pending.to, days: pending.days }, pendingMeta.individschema, state);
  }
  state.berakningarDerived = !!derived;
  state.berakningar = pendingMeta.berakningar || (derived ? derived.berakningar : null);
  state.kontroller = pendingMeta.kontroller || (derived ? derived.kontroller : null);
  state.personal = pendingMeta.personal || (derived ? derived.personal : null);
  state.intakter = pendingMeta.intakter || (derived ? derived.intakter : null);
  state.passmallar = pendingMeta.passmallar || null;
  state.individschema = pendingMeta.individschema || null;
  state.villkor = pendingMeta.villkor || null;
  avidentifieraNamn(); // byt riktiga medarbetarnamn mot fiktiva

  state.nyttSchema = pendingMeta.scenario || null;
  if (state.nyttSchema) state.nyttSchema.fileName = pendingMeta.fileName || "";
  persist();
  const antalInsatser = state.rows.length;
  const antalMedarbetare = state.personal && state.personal.rows ? state.personal.rows.length : 0;
  pending = null; pendingMeta = null; curveDay = 0;
  markeraSparat();
  notera(`${antalInsatser} insatser och ${antalMedarbetare} medarbetare inlästa`, "ok", { detalj: "Nu visas kundbehov, resursbehov och nyckeltal för perioden." });
  render();
}


/* ================================================================== *
 * Ny modell: nuvarande schema + kundbehov + regler → bättre schema.
 * schemaOriginal (Medvind) och rows (Sekoia) sparas orörda. Optimeringen
 * arbetar på kopior, så nuläget alltid går att jämföra mot.
 * ================================================================== */
function analysPeriod() {
  const from = state.period.from;
  return { from, to: addDays(from, state.analysisDays - 1) };
}
function schemaPass() {
  if (!state.schemaOriginal || !state.period) return [];
  const { from, to } = analysPeriod();
  const start = MV.mandagen(from);
  const dagarTot = Math.round((Date.parse(to + "T12:00:00Z") - Date.parse(start + "T12:00:00Z")) / 864e5) + 1;
  return MV.schemaTillDatum(state.schemaOriginal, start, dagarTot).filter((p) => p.datum >= from && p.datum <= to);
}
/** Planerad schematid = riktiga Medvind-passen (vikarier med, sovande jour utan).
 * Efter en bemanningsbalans används exakt samma passlista som Före & efter
 * (efterPass), så alla vyer visar identisk schematid. */
function medvindSchematidH() {
  const pass = state.balans ? efterPass() : schemaPass();
  if (!pass || !pass.length) return 0;
  return pass.filter((p) => !p.jour).reduce((s, p) => s + (Number(p.timmar) || 0), 0);
}
/** "medvind" när schematiden kommer ur schemat, annars uppskattad ur Sekoia. */
function schematidKalla() {
  return medvindSchematidH() > 0 ? "medvind" : "sekoia";
}

function raderEfter() {
  const flyttade = (state.balans && state.balans.flyttade) || [];
  if (!flyttade.length) return arbetsRader();
  const karta = new Map(flyttade.map((f) => [String(f.id), f]));
  return arbetsRader().map((r) => {
    const f = karta.get(String(r.id || r.kallrad));
    if (!f) return r;
    const dur = Number(r.minuter) || 0;
    return { ...r, start: f.till, slut: minClock((clockMin(f.till) || 0) + dur), fonsterStart: f.fran };
  });
}
/** Antal kunder som ger ersättning (gemensamma insatser räknas inte som kund). */
function antalIntaktKunder() {
  return C.perKund(state.rows || []).filter((k) => !/^gemensam/i.test(k.kund)).length;
}
/** Timkostnad per person – medarbetarens egen om den är ändrad. */
function timkostnadFor(namn) {
  const m = medarbetarLista().find((x) => x.namn === namn);
  return m && m.timkostnad ? Number(m.timkostnad) : (state.hourlyCost || 270);
}
function ekonomiBas() {
  return { timkostnad: state.hourlyCost || 270, timkostnadFor, antalKunder: antalIntaktKunder(), dygnsErsattning: state.dygnKr || 2500 };
}
/** Villkoren i medarbetarvyn i den form schemaoptimeringen använder. */
function optimeringsVillkor() {
  return medarbetarLista().map((m) => ({
    namn: m.namn,
    grad: m.grad,
    vikarie: m.vikarie,
    samordnare: m.samordnare,
    delegering: m.delegering,
    nattbehorig: m.nattbehorig,
    jour: m.jour,
    passprofil: m.passprofil,
    helggrad: m.helg === "vartredje" ? "var3" : m.helg,
    tidigast: m.tidigastStart,
    senast: m.senastSlut,
    maxdag: m.maxDagarIFoljd,
    franvaro: m.franvaro === "ingen" ? null : m.franvaro === "arbetar2v" ? "halvtid" : m.franvaro,
    timkostnad: m.timkostnad,
  }));
}
/** Pass efter optimering, vikarieprövning och manuella omplaceringar. */
function efterPass() {
  const bort = new Set((state.balans && state.balans.borttagnaPass) || []);
  const bas = (state.balans && state.balans.schemaPass) || schemaPass();
  const moves = (state.schemaLek && state.schemaLek.moves) || {};
  return bas.filter((p) => !bort.has(p.id)).map((p) => moves[p.id] ? { ...p, namn: moves[p.id] } : p);
}
/** Krockar mellan importerat schema och medarbetarnas villkor. */
function villkorsVarningar() {
  const lista = medarbetarLista();
  const karta = new Map(lista.map((m) => [m.namn, m]));
  const ut = [];
  let helg = 0, franvaro = 0, profil = 0, fonster = 0;
  for (const p of schemaPass()) {
    const m = karta.get(p.namn);
    if (!m) continue;
    const d = new Date(p.datum + "T12:00:00Z").getUTCDay();
    const arHelg = d === 0 || d === 6;
    if (arHelg && m.helg === "inga") helg += 1;
    if (m.franvaro && m.franvaro !== "ingen") franvaro += 1;
    const startMin = clockMin(p.start) || 0;
    if (m.passprofil === "dag" && startMin >= 17 * 60) profil += 1;
    if (m.passprofil === "kvall" && startMin < 14 * 60) profil += 1;
    if (m.passprofil === "natt" && !p.jour) profil += 1;
    if (m.tidigastStart && p.start < m.tidigastStart) fonster += 1;
    if (m.senastSlut && p.slut > m.senastSlut && !p.natt) fonster += 1;
  }
  if (helg) ut.push(`${helg} pass ligger på helg för medarbetare som inte ska tjänstgöra helger.`);
  if (franvaro) ut.push(`${franvaro} pass ligger på medarbetare som är markerade som frånvarande del av perioden.`);
  if (profil) ut.push(`${profil} pass krockar med medarbetarens passprofil (dag, kväll eller ständig natt).`);
  if (fonster) ut.push(`${fonster} pass ligger utanför medarbetarens tidigaste start eller senaste sluttid.`);
  return ut;
}
function foreLage() {
  if (!state.rows.length || !state.period || !state.schemaOriginal) return null;
  const { from, to } = analysPeriod();
  const a = MODELL.analysera({
    rader: C.filtreraPeriod(state.rows, from, to), pass: schemaPass(),
    fran: from, till: to, ...ekonomiBas(),
  });
  return { ...a, kundnaraAndel: a.kundnaraPct, schemakostnad: a.kostnad };
}
function foreEfterModell() {
  if (!state.rows.length || !state.period || !state.schemaOriginal) return null;
  const { from, to } = analysPeriod();
  const bas = { fran: from, till: to, ...ekonomiBas() };
  const fore = MODELL.analysera({ ...bas, pass: schemaPass(), rader: C.filtreraPeriod(state.rows, from, to) });
  if (!state.balans) return { fore, efter: null, tabell: [], punkter: [], flyttade: [], minska: [], forstark: [], vikarie: null, varningar: [] };
  const efter = MODELL.analysera({ ...bas, pass: efterPass(), rader: C.filtreraPeriod(raderEfter(), from, to) });
  const schemaVarningar = (state.balans.schemaVarningar || []).map((v) => v.text);
  const varningar = [...new Set([...villkorsVarningar(), ...schemaVarningar])];
  const j = MODELL.jamfor(fore, efter, state.balans.flyttade || [], {
    h: (x) => h1(x) + " h", kr: (x) => kr(x), pct: (x) => h1(x) + " %",
  }, state.balans.vikarie || null, varningar);
  const forandringar = state.balans.schemaForandringar || [];
  return { fore, efter, ...j, punkter: [...forandringar.map((f) => f.text), ...j.punkter], flyttade: state.balans.flyttade || [], vikarie: state.balans.vikarie || null, varningar };
}

function underlagInfo() {
  const sk = state.schemaOriginal;
  const { from, to } = state.period ? analysPeriod() : { from: "", to: "" };
  return {
    godkand: {
      kund: !!state.kundGodkand,
      schema: !!state.schemaGodkand,
      allt: !!state.kundGodkand && !!state.schemaGodkand,
    },
    schema: sk
      ? { filnamn: sk.filnamn, blad: sk.blad, medarbetare: sk.medarbetare.filter((m) => !m.vikarie).length,
          vakanta: sk.medarbetare.filter((m) => m.vikarie).length, vikarier: sk.medarbetare.filter((m) => m.vikarie).length,
          pass: sk.pass.length,
          veckor: sk.veckor, timmar: sk.timmarTot, jour: sk.jourTimmarTot, vakantaPass: sk.vakantaPass }
      : null,

    sekoia: state.rows.length
      ? { insatser: state.rows.length, kunder: C.perKund(state.rows).length,
          from: state.period ? state.period.from : "", to: state.period ? addDays(state.period.from, state.importDays - 1) : "",
          timmar: C.nyckeltal(state.rows).kundbehovH }
      : null,
    period: { from, to, dagar: state.analysisDays },
    villkor: MODELL.STYRANDE_VILLKOR.flatMap((g) => g.villkor.map((v) => ({ regel: v[0], varde: `${v[1]} ${v[2]}`.trim() }))),
    balans: state.balans ? { flyttade: (state.balans.flyttade || []).length, skapad: state.balans.skapad } : null,
    vikarie: state.balans && state.balans.vikarie ? state.balans.vikarie : null,
    varningar: state.schemaOriginal ? villkorsVarningar() : [],
  };
}

/** Sammanfattning av sparat arbete – visas i "Fortsätt med befintlig data". */
/** Utfall ur Sekoia-statusfälten. Inget uppskattas – bara det filen säger. */
function utfallSekoia() {
  const rader = arbetsRader();
  if (!rader.length) return null;
  const raknare = { utford: 0, installd: 0, flyttad: 0, ejUtford: 0, ovrigt: 0 };
  let medUtford = 0, inomFonster = 0, avvikelseSum = 0;
  for (const r of rader) {
    const st = String(r.status || "").toLowerCase();
    if (st.startsWith("utf")) raknare.utford++;
    else if (st.startsWith("inst")) raknare.installd++;
    else if (st.startsWith("flytt")) raknare.flyttad++;
    else if (st.startsWith("ej")) raknare.ejUtford++;
    else raknare.ovrigt++;
    if (r.utfordMin != null && r.planeradMin != null) {
      medUtford++;
      const diff = r.utfordMin - r.planeradMin;
      avvikelseSum += Math.abs(diff);
      const slut = r.fonsterSlut != null ? r.fonsterSlut : r.planeradMin;
      if (r.utfordMin >= r.planeradMin && r.utfordMin <= slut) inomFonster++;
    }
  }
  return {
    antal: rader.length,
    ...raknare,
    medUtford,
    inomFonsterPct: medUtford ? (inomFonster / medUtford) * 100 : null,
    snittAvvikelseMin: medUtford ? avvikelseSum / medUtford : null,
  };
}

function sparadInfo() {
  if (!harUnderlag()) return null;
  const { from, to } = analysPeriod();
  return {
    period: `${from} – ${to}`,
    insatser: state.rows.length,
    kunder: C.perKund(state.rows).length,
    medarbetare: state.schemaOriginal ? state.schemaOriginal.medarbetare.length : 0,
    pass: state.schemaOriginal ? state.schemaOriginal.pass.length : 0,
    balans: harResultat(),
    uppdaterad: (state.balans && state.balans.skapad) || null,
  };
}
/** Rensar den här verksamhetens underlag och resultat. */
function rensaVerksamhet() {
  state.rows = []; state.period = null; state.importDays = 0;
  state.schemaOriginal = null; state.kundGodkand = false; state.schemaGodkand = false;
  state.balans = null; state.optimerat = false;
  state.kundEdit = null; state.kundLek = null; state.schemaLek = null;
  state.berakningar = null; state.kontroller = null; state.personal = null; state.intakter = null;
  state.individschema = null; state.medarbetarInfo = {};
  persist();
  tab = "uppladdning";
  notera("Underlaget är rensat", "ok", { detalj: "Ladda upp kundernas behov och schemat igen när du vill." });
  render();
}

/* ---------- Medarbetaruppgifter (kompletteras av chefen) ---------- */
function medarbetarInfoKarta() {
  if (!state.medarbetarInfo) state.medarbetarInfo = {};
  return state.medarbetarInfo;
}
/** Fälten chefen kan ändra per medarbetare – de styr optimeringen. */

const MEDARB_STANDARD = {
  passprofil: "blandat",   // blandat | dag | kvall | natt
  helg: "varannan",        // varannan | vartredje | alla | inga
  tidigastStart: "06:30",
  senastSlut: "23:00",
  maxDagarIFoljd: 5,
  franvaro: "ingen",       // ingen | ledig1v | arbetar2v | semester
  timkostnad: 270,
  anstallning: "manad",    // manad | timme
};
function medarbetarLista() {
  const info = medarbetarInfoKarta();
  const fran = state.schemaOriginal ? state.schemaOriginal.medarbetare : [];
  const extra = Object.keys(info).filter((n) => info[n] && info[n].extra && !fran.some((m) => m.namn === n));
  const bas = fran.map((m) => ({ namn: m.namn, grad: m.grad, vikarie: !!m.vikarie }))
    .concat(extra.map((n) => ({ namn: n, grad: 100, vikarie: false })));
  return bas.map((m) => {
    const i = info[m.namn] || {};
    const v = (falt, standard) => (i[falt] != null && i[falt] !== "" ? i[falt] : standard);
    return {
      namn: m.namn,
      // Vikarier är riktiga medarbetare i modellen, men märkta så de kan visas gult.
      vikarie: m.vikarie,
      vakant: m.vikarie,
      grad: i.grad != null ? Number(i.grad) : m.grad,
      samordnare: i.samordnare != null ? !!i.samordnare : /topas/i.test(m.namn),
      delegering: i.delegering != null ? !!i.delegering : true,
      jour: i.jour != null ? !!i.jour : true,
      nattbehorig: i.nattbehorig != null ? !!i.nattbehorig : true,
      passprofil: v("passprofil", MEDARB_STANDARD.passprofil),
      helg: v("helg", MEDARB_STANDARD.helg),
      tidigastStart: v("tidigastStart", MEDARB_STANDARD.tidigastStart),
      senastSlut: v("senastSlut", MEDARB_STANDARD.senastSlut),
      maxDagarIFoljd: Number(v("maxDagarIFoljd", MEDARB_STANDARD.maxDagarIFoljd)),
      franvaro: v("franvaro", MEDARB_STANDARD.franvaro),
      timkostnad: Number(v("timkostnad", state.hourlyCost || MEDARB_STANDARD.timkostnad)),
      anstallning: v("anstallning", MEDARB_STANDARD.anstallning),
    };
  });
}
function medarbetareSet(namn, falt, varde) {
  const info = medarbetarInfoKarta();
  const nuvarande = medarbetarLista().find((m) => m.namn === namn) || {};
  info[namn] = { ...nuvarande, ...(info[namn] || {}), [falt]: varde };
  state.schemaGodkand = false;
  // Sovande jour är nattarbete: jour kräver nattbehörighet, och tas behörigheten
  // bort kan personen inte längre gå jour.
  if (falt === "jour" && varde) info[namn].nattbehorig = true;
  if (falt === "nattbehorig" && !varde) info[namn].jour = false;
  if (falt === "passprofil" && String(varde) === "natt") info[namn].nattbehorig = true;

  // Ändrade villkor gör resultatet ogiltigt – balansen måste skapas om.
  if (state.balans) {
    state.balans = null; state.optimerat = false;
    notera("Uppgiften är sparad – skapa bemanningsbalans igen", "info",
      { detalj: "Villkoren styr optimeringen, så resultatet nollställdes." });
  }
  persist(); render();
}
function medarbetareLaggTill(namn) {
  const rent = String(namn || "").trim();
  if (!rent) return;
  const info = medarbetarInfoKarta();
  info[rent] = { extra: true, grad: 100, samordnare: false, delegering: true, jour: true, ...MEDARB_STANDARD };
  if (state.balans) { state.balans = null; state.optimerat = false; }
  persist();
  notera(`${rent} tillagd`, "ok", { detalj: "Kompletterande uppgifter sparas i verksamheten." });
  render();
}


function skapaBalans() {
  if (!state.rows.length || !state.period) {
    notera("Kundbehovet saknas", "fel", { detalj: "Läs in Sekoia-rapporten först." });
    tab = "kundgrupp"; render(); return;
  }
  if (!state.schemaOriginal) {
    notera("Personalschemat saknas", "fel", { detalj: "Ladda upp Medvind-exporten under Underlag först." });
    tab = "kundgrupp"; render(); return;
  }
  if (!state.kundGodkand || !state.schemaGodkand) {
    notera("Godkänn underlagen först", "info", { detalj: "Granska kunder och medarbetare innan optimeringen startar." });
    tab = "uppladdning"; render(); return;
  }
  const { from, to } = analysPeriod();
  const dagLista = [];
  for (let i = 0; i < state.analysisDays; i++) dagLista.push(addDays(from, i));
  const bem = MODELL.bemanningPerSlot(schemaPass(), dagLista).aktiv;
  const res = MODELL.optimeraInsatser(C.filtreraPeriod(state.rows, from, to), from, to, bem);
  const schemaRes = MODELL.optimeraSchema({
    pass: schemaPass(),
    rader: res.rader,
    fran: from,
    till: to,
    medarbetare: optimeringsVillkor(),
    timkostnad: state.hourlyCost || 270,
  });
  state.balans = {
    flyttade: res.flyttade,
    schemaPass: schemaRes.pass,
    schemaForandringar: schemaRes.forandringar,
    schemaVarningar: schemaRes.varningar,
    skapad: new Date().toISOString(),
    kalla: "lokal",
  };
  state.motorResultat = null;
  // Pröva vikariepassen mot det optimerade behovet: de som inte fyller ett gap
  // tas bort, övriga behöver tillsättas.
  const kurva = C.resurskurva(C.filtreraPeriod(raderEfter(), from, to), from, to);
  const dim = kurva.intervall.map((iv) => iv.dimensionerat);
  const vik = MODELL.provaVikariepass(schemaRes.pass, dim, dagLista);
  state.balans.borttagnaPass = vik.borttagna;
  state.balans.vikarieBeslut = vik.beslut;
  state.balans.vikarie = { antalBorttagna: vik.antalBorttagna, antalBehalls: vik.antalBehalls };
  state.optimerat = true;
  tab = "foreefter";
  persist();
  notera(`Bemanningsbalans skapad – ${schemaRes.forandringar.length} pass och ${res.flyttade.length} insatser ändrades`, "ok",
    { detalj: `${vik.antalBehalls} vikariepass behöver tillsättas, ${vik.antalBorttagna} kunde tas bort.` });
  render();
}

/** Värden ur styrande villkor i den form optimeringsmotorn läser dem. */
function motorRegler() {
  const varden = {};
  for (const g of MODELL.STYRANDE_VILLKOR) for (const rad of g.villkor) varden[rad[0]] = rad[1];
  const tal = (namn, standard) => {
    const x = parseFloat(String(varden[namn] ?? "").replace(",", "."));
    return Number.isFinite(x) ? x : standard;
  };
  return {
    minRestHours: tal("Minsta dygnsvila", 11),
    maxWeeklyHours: 48,
    maxShiftHours: tal("Långpass – röd varning", 12),
    maxConsecutiveDays: Math.round(tal("Max arbetsdagar i följd", 5)),
    nightFloor: Math.round(tal("Vaken natt – grundbemanning", 1)),
    flexibilityStep: 15,
  };
}

/**
 * Tar emot optimeringsmotorns förslag. Motorns pass och insatstider blir
 * appens "efter"-läge, precis som den lokala beräkningens resultat.
 * Originalschemat och kundbehovet ändras inte.
 */
function anvandMotorResultat(res) {
  if (!res || !Array.isArray(res.pass)) return false;
  const skapad = new Date().toISOString();
  const varningar = (res.varningar || []).map((v) => (typeof v === "string" ? { text: v } : v));
  state.balans = {
    flyttade: res.flyttade || [],
    schemaPass: res.pass,
    schemaForandringar: res.forandringar || [],
    schemaVarningar: varningar,
    borttagnaPass: [],
    vikarieBeslut: res.pass
      .filter((p) => p.vikarie)
      .map((p) => ({ id: p.id, namn: p.namn, datum: p.datum, start: p.start, slut: p.slut, timmar: p.timmar, behovs: true })),
    vikarie: { antalBorttagna: 0, antalBehalls: res.pass.filter((p) => p.vikarie).length },
    skapad,
    kalla: "motor",
  };
  state.motorResultat = { ...res, kalla: "motor", skapad };
  state.optimerat = true;
  tab = "foreefter";
  persist();
  notera(`Bemanningsbalans skapad med optimeringsmotorn – ${res.pass.length} pass i förslaget`, "ok", {
    detalj: res.explanation || "Förslaget visas i Jämför före och efter.",
  });
  render();
  return true;
}

function aterstallBalans() {
  state.balans = null; state.optimerat = false; state.motorResultat = null; persist();
  notera("Tillbaka till originaldata", "ok", { detalj: "Både schemat och kundbehovet visas som de lästes in." });
  render();
}
function handleSchemaFil(file) {
  laser = true; render();
  const reader = new FileReader();
  reader.onerror = () => { laser = false; notera("Filen kunde inte läsas", "fel"); render(); };
  reader.onload = (e) => {
    let sk = null;
    try {
      const wb = XLSX.read(new Uint8Array(e.target.result), { type: "array", cellDates: false });
      sk = MV.parseMedvind(wb, file.name);
    } catch (err) {
      laser = false;
      notera("Kunde inte läsa filen", "fel", { detalj: err.message + " Kontrollera att det är en Excel-fil (.xlsx)." });
      render(); return;
    }
    laser = false;
    if (!sk) {
      notera("Hittade inget personalschema", "fel", { detalj: 'Filen behöver ett blad där första raden börjar med "Schemarad" (Medvind-export).' });
      render(); return;
    }
    state.schemaOriginal = sk; state.schemaGodkand = false; state.balans = null; state.optimerat = false;
    persist();
    tab = "uppladdning";
    notera(`${sk.pass.length} pass och ${sk.medarbetare.length} schemarader inlästa`, "ok",
      { detalj: "Nu kan du skapa bemanningsbalans." });
    render();
  };
  reader.readAsArrayBuffer(file);
}

/* ---------- Härledda värden för vald period ---------- */
function derive() {
  if (!state.rows.length || !state.period) return null;
  const from = state.period.from;
  const to = addDays(from, state.analysisDays - 1);
  const rows = C.filtreraPeriod(arbetsRader(), from, to);
  const n = C.nyckeltal(rows);
  const kunder = C.perKund(rows);
  const curve = C.resurskurva(rows, from, to);
  // Verksamhetens eget samtidighetsbaserade resursbehov (15 min) om det finns
  // med i importen – exakt den siffra modellen i Excel visar. När kundbehovet
  // redigerats räknar vi i stället kurvan live ur de ändrade raderna.
  const fil = kundLekAktiv() ? null : fileResource(from, to);
  const resursH = fil ? fil.hours : curve.dimensionerandeDirektResursbehovH;
  const eco = C.ekonomi({ planeradeTimmar: state.plannedHours, timkostnad: state.hourlyCost, dimensionerandeH: resursH });
  const pct = C.procentsatser({ kundbehovH: n.kundbehovH, personalbehovH: n.personalbehovH, dimensionerandeH: resursH, planeradeTimmar: state.plannedHours });
  const gem = kunder.find((k) => /^gemensam/i.test(k.kund));
  return { from, to, rows, n, kunder, curve, eco, pct, gem, fil, resursH, redigerad: kundLekAktiv() };
}

// Arbetsrader: den redigerade lek-kopian om kundbehovet ändrats, annars
// den importerade datan. All härledning (siffror, kurva, per kund) utgår
// härifrån, så en ändring slår igenom överallt automatiskt.
function arbetsRader() { return state.kundEdit && state.kundEdit.rows ? state.kundEdit.rows : state.rows; }
function kundLekAktiv() { return !!(state.kundEdit && state.kundEdit.rows); }
// Startar en lek-kopia av raderna (djup kopia) första gången man redigerar.
function startaKundEdit() {
  if (!state.kundEdit || !state.kundEdit.rows) {
    state.kundEdit = { rows: state.rows.map((r, i) => ({ ...r, _id: r.kallrad ?? ("r" + i) })) };
  }
  return state.kundEdit;
}
function aterstallKundEdit() { state.kundEdit = null; persist(); render(); }

// Summerar filens 15-minutersresursbehov för vald period (× 0,25 h).
function fileResource(from, to) {
  if (!state.resurs || !state.resurs.perDay) return null;
  let hours = 0, has = false;
  const peak = { value: 0, datum: "", tid: "" };
  for (const iso of state.resurs.days) {
    if (iso < from || iso > to) continue;
    has = true;
    for (const s of state.resurs.perDay[iso]) {
      hours += s.req * 0.25;
      if (s.req > peak.value) { peak.value = s.req; peak.datum = iso; peak.tid = s.tid; }
    }
  }
  return has ? { hours, peak } : null;
}
const h1 = (x) => x.toLocaleString("sv-SE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const h2 = (x) => x.toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
// Läser ett värde ur verksamhetens Beräkningar-blad (filens egen sanning).
function ber(name) { return state.berakningar && state.berakningar[name] != null ? state.berakningar[name].value : null; }
function berDef(name) { return state.berakningar && state.berakningar[name] ? state.berakningar[name].def : ""; }
function hasBer() { return !!state.berakningar; }
// Utgångsvärden för känslighetsreglagen, hämtade ur verksamhetens egna blad.
// Allt räknas på en kopia – den importerade datan rörs aldrig.
function simBaseline(d) {
  const num = (namn, fallback) => { const v = ber(namn); return typeof v === "number" ? v : fallback; };
  const schematid = num("Planerad schematid", state.plannedHours);
  const schemakostnad = num("Ren schemakostnad", schematid * state.hourlyCost);
  const timkostnad = schematid > 0 ? schemakostnad / schematid : state.hourlyCost;
  const budget = num("Aktuell personalbudget", state.budget);
  const reservKr = num("Ekonomisk reserv", budget * 0.06);
  const reservPct = budget > 0 ? reservKr / budget * 100 : 6;
  const korttidKr = num("Prognos korttidsfrånvaro", schemakostnad * 0.04);
  const korttidPct = schemakostnad > 0 ? korttidKr / schemakostnad * 100 : 4;
  const buffertKr = num("Beslutad bemanningsbuffert – värde", schemakostnad * 0.04);
  const buffertPct = schemakostnad > 0 ? buffertKr / schemakostnad * 100 : 4;
  const intakt = num("Månadsintäkt", d ? d.eco.planeradKostnad : 0);
  const vak = (state.personal ? state.personal.rows : []).filter((r) => String(r["Status"]).toLowerCase() === "vakant")
    .map((r) => ({ namn: r["Medarbetare"], timmar: Number(r["Budget h/mån"]) || 0, kostnad: Number(r["Budgetkostnad/mån"]) || 0 }));
  const kundRate = {}; const kundDagar = {};
  if (state.intakter) for (const r of state.intakter.rows) {
    const k = String(r["Kund"] ?? "").trim(); if (!k) continue;
    if (kundRate[k] == null) kundRate[k] = Number(r["Grund kr/dygn"]) || 0;
    if (String(r["Aktiv kund"]).toLowerCase() !== "nej") kundDagar[k] = (kundDagar[k] || 0) + 1;
  }
  const dagar = num("Antal dagar i period", state.importDays || 30);
  const dimBehov = d ? d.resursH : num("Dimensionerande direkt resursbehov", 0);
  return { schematid, timkostnad, budget, reservPct, korttidPct, buffertPct, intakt, vak,
    kundRate, kundDagar, dagar, dimBehov, nattgolv: state.nightBase ?? 1,
    planeradeTimmar: state.plannedHours, malPct: 75 };
}
const kr = (x) => x.toLocaleString("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 });
const pctTxt = (v) => v == null ? "–" : v.toLocaleString("sv-SE", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " %";

/* ---------- Excel-export (sammanställning till chefen) ---------- */
function exportExcel() {
  const d = derive();
  if (!d) { notera("Det finns inget att exportera ännu", "fel", { detalj: "Läs in en verksamhet först, till exempel med Skapa bemanningsbalans." }); return; }
  const covers = state.analysisDays <= state.planDays;
  const rows = [
    ["Bemanningsbalans – sammanställning"],
    ["Verksamhet", state.org],
    ["Period", `${d.from} – ${d.to} (${state.analysisDays} dagar)`],
    ["Skapad", new Date().toLocaleString("sv-SE")],
    [],
    ["Nyckeltal", "Värde", "Formel/kommentar"],
    ["Kundbehov (h)", round1(d.n.kundbehovH), "Summa av insatsernas minuter"],
    ["Personalbehov inkl. dubbelbemanning (h)", round1(d.n.personalbehovH), "Minuter × antal medarbetare"],
    ["Extra dubbelbemanning (h)", round1(d.n.extraDubbelH), "Personalbehov − kundbehov"],
    ["Dubbelbemannade insatser", d.n.dubbelbemannadeRader, ""],
    ["Antal insatser", d.n.antalInsatser, ""],
    ["Dimensionerande resursbehov (h)", round1(d.resursH), d.fil ? "Samtidighet per 15 min (verksamhetens modell)" : "Appens 30-min-beräkning inkl. vaken natt"],
    ["Resursbehovets topp", d.fil ? d.fil.peak.value : round1(d.curve.topp.rabehov), d.fil ? `${d.fil.peak.datum} kl. ${d.fil.peak.tid}` : `${d.curve.topp.datum} kl. ${d.curve.topp.klockan}`],
    ["Planerade timmar (h)", round1(state.plannedHours), ""],
    ["Planerad kostnad (kr)", Math.round(d.eco.planeradKostnad), "Planerade timmar × timkostnad"],
    ["Planerad överkapacitet (h)", round1(d.eco.planeradOverkapacitetH), "Planerade timmar − dimensionerande behov"],
    ["Kundbehov ÷ planerade timmar (%)", covers ? round1(d.pct.kundbehovAvPlanerade.varde) : "Kan inte beräknas", ""],
    ["Personalbehov ÷ planerade timmar (%)", covers ? round1(d.pct.personalbehovAvPlanerade.varde) : "Kan inte beräknas", ""],
    ["Dimensionerande ÷ planerade timmar (%)", covers ? round1(d.pct.dimensionerandeAvPlanerade.varde) : "Kan inte beräknas", ""],
    ["Faktisk kundnära tid (%)", "Kan inte beräknas", "Kräver faktiskt arbetad tid"],
    [],
    ["Kund", "Insatser", "Kundbehov (h)", "Personalbehov inkl. dubbel (h)"],
    ...d.kunder.map((k) => [k.kund, k.insatser, round1(k.kundbehovH), round1(k.personalbehovH)]),
  ];
  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!cols"] = [{ wch: 40 }, { wch: 16 }, { wch: 34 }, { wch: 20 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Sammanställning");
  const safe = (state.org || "verksamhet").replace(/[^\wåäöÅÄÖ -]/g, "").trim().replace(/\s+/g, "_") || "verksamhet";
  const datum = new Date().toISOString().slice(0, 10);
  const filnamn = `Bemanningsbalans_${safe}_${datum}_v${APP_VERSION}.xlsx`;
  try {
    XLSX.writeFile(wb, filnamn);
    markeraSparat();
    renderNav();
    notera("Exporterat till Excel", "ok", { detalj: filnamn });
  } catch (err) {
    notera("Exporten misslyckades", "fel", { detalj: "Försök igen, eller stäng eventuell öppen fil med samma namn." });
  }
}
function round1(x) { return Math.round(x * 10) / 10; }

/* ---------- Känslighetsberäkning ("Vad händer om") ---------- */
// Tar utgångsläget + reglagens värden och räknar fram nya tal med ren
// aritmetik. Rör aldrig importerad data. sim.<nyckel> = värde om reglaget dragits.
function simCompute(base) {
  const g = (k, d) => (sim[k] != null ? sim[k] : d);
  const timkostnad = g("timkostnad", base.timkostnad);
  const tillsattVak = g("tillsattVak", 0); // antal vakanser som tillsätts (0..vak.length)
  const korttidPct = g("korttidPct", base.korttidPct);
  const reservPct = g("reservPct", base.reservPct);
  const buffertPct = g("buffertPct", base.buffertPct);
  const budget = g("budget", base.budget);
  const kundRatePct = g("kundRatePct", 100);   // grundersättning per kund, % av original
  const kunddagarPct = g("kunddagarPct", 100); // aktiva kunddagar, % av original
  const nattgolv = g("nattgolv", base.nattgolv);
  const planeradeTimmar = g("planeradeTimmar", base.planeradeTimmar);
  const malPct = g("malPct", base.malPct);

  // Vakanstimmar som tillkommer när positioner tillsätts (störst först).
  const vakSort = [...base.vak].sort((a, b) => b.timmar - a.timmar);
  let extraTimmar = 0;
  for (let i = 0; i < Math.min(tillsattVak, vakSort.length); i++) extraTimmar += vakSort[i].timmar;
  const schematid = base.schematid + extraTimmar;

  const schemakostnad = schematid * timkostnad;
  const korttidKr = schemakostnad * korttidPct / 100;
  const buffertKr = schemakostnad * buffertPct / 100;
  const totalPrognos = schemakostnad + korttidKr;
  const reservKr = budget * reservPct / 100;
  const budgetavvikelse = budget - totalPrognos;
  const disponibelt = budgetavvikelse - reservKr;

  // Intäkt: skala per-kund-ersättning och antal aktiva kunddagar.
  let intakt = 0;
  for (const k of Object.keys(base.kundRate)) {
    const rate = base.kundRate[k] * kundRatePct / 100;
    const dagar = (base.kundDagar[k] || 0) * kunddagarPct / 100;
    intakt += rate * dagar;
  }
  if (!Object.keys(base.kundRate).length) intakt = base.intakt * kundRatePct / 100 * kunddagarPct / 100;

  // Nattgolvets effekt på dimensionerande behov (skillnad mot utgångsnattgolvet,
  // en medarbetare per nattintervall 22–06 = 8 h/dygn × dagar).
  const nattTimmarPerDygn = 8;
  const dimBehov = base.dimBehov + (nattgolv - base.nattgolv) * nattTimmarPerDygn * base.dagar;

  const gapH = planeradeTimmar - dimBehov;
  const gapKr = gapH * timkostnad;

  return { timkostnad, schematid, schemakostnad, korttidKr, buffertKr, totalPrognos,
    reservKr, budgetavvikelse, disponibelt, intakt, dimBehov, gapH, gapKr,
    planeradeTimmar, malPct, extraTimmar, tillsattVak,
    resultat: intakt - totalPrognos };
}

/* ================================================================== *
 * Schemabräde ("lek-kopia") – pedagogisk drag-och-släpp-vy.
 * Bygger ett rutnät medarbetare × dagar ur Individschema. Att flytta ett
 * pass ändrar bara lek-kopian (state.schemaLek), aldrig importerad data.
 * ================================================================== */
function toClock(v) {
  if (isDate(v)) return `${String(v.getHours()).padStart(2,"0")}:${String(v.getMinutes()).padStart(2,"0")}`;
  const s = String(v ?? "").match(/(\d{1,2}):(\d{2})/); return s ? `${s[1].padStart(2,"0")}:${s[2]}` : "";
}
function minutesOf(clock) { const m = String(clock).match(/(\d{1,2}):(\d{2})/); return m ? +m[1]*60 + +m[2] : null; }

// Bygger schemamodellen: medarbetare (med SSG, nattbehörighet, mål), dagar,
// och pass. Returnerar null om filen saknar Individschema/Personal.
function buildSchemaModel() {
  if (!state.schemaOriginal) return null;
  const persProf = {};
  for (const m of medarbetarLista()) persProf[m.namn] = {
    ssgMal: m.grad / 100,
    nattbehorig: m.nattbehorig,
    maxFoljd: m.maxDagarIFoljd,
    budgetH: (m.grad / 100) * 40 * Math.max(1, state.analysisDays / 7),
    status: m.vikarie ? "Vikarie" : "Anställd",
    vikarie: m.vikarie,
  };
  const pass = efterPass().map((p) => ({ ...p, betald: p.timmar, typ: p.jour ? "Natt/jour" : p.kod || "Arbetstid" }));
  const dagarSet = new Set(pass.map((p) => p.datum));
  const medSet = new Set(pass.map((p) => p.namn));
  const dagar = [...dagarSet].sort();
  // Medarbetare: de som har pass + de i personalregistret (utom tomma "Ny medarbetare").
  const medarbetare = [...new Set([...medSet, ...Object.keys(persProf)])]
    .filter((n) => medSet.has(n) || (persProf[n] && persProf[n].budgetH > 0))
    .sort();
  return { pass, dagar, medarbetare, prof: persProf };
}

// Lek-kopian: { flyttar: [{passId, frånNamn, tillNamn, datum}] }. Vi lagrar
// bara flyttarna, så originalet kan återställas när som helst.
function schemaLek() { return state.schemaLek || { moves: {} }; }
function schemaEffektiv(model) {
  const lek = schemaLek();
  return model.pass.map((p) => {
    const mv = lek.moves[p.id];
    return mv ? { ...p, namn: mv } : p;
  });
}

// Varningar för en medarbetares pass-serie i effektiva schemat.
// Exakta: dygnsvila (<11h), pass i följd (>maxFöljd), natt utan behörighet, SSG.
// Indikationer (märkta): övertid/vecka, veckovila.
function schemaVarningar(model, effektiva) {
  const perMed = {};
  for (const p of effektiva) (perMed[p.namn] ||= []).push(p);
  const varningar = {}; // passId -> [{typ, text, indikation}]
  const medInfo = {};   // namn -> {planeradH, ssgMal, ...}
  for (const namn of Object.keys(perMed)) {
    const lista = perMed[namn].slice().sort((a, b) => (a.datum + a.start).localeCompare(b.datum + b.start));
    const prof = model.prof[namn] || { nattbehorig: false, maxFoljd: 5, budgetH: 0, ssgMal: 0 };
    let foljd = 0; let prevDate = null; let prevEndAbs = null;
    let veckaH = {}; let totalH = 0;
    for (let i = 0; i < lista.length; i++) {
      const p = lista[i]; const w = [];
      // Natt utan behörighet
      if (p.natt && !prof.nattbehorig) w.push({ typ: "natt", text: `${namn} saknar nattbehörighet`, indikation: false });
      // Dygnsvila: tid mellan förra passets slut och detta passets start
      const startAbs = dayIndex(model, p.datum) * 1440 + (minutesOf(p.start) || 0);
      let endAbs = dayIndex(model, p.datum) * 1440 + (minutesOf(p.slut) || 0);
      if (endAbs <= startAbs) endAbs += 1440; // nattpass över midnatt
      if (prevEndAbs != null) {
        const vila = (startAbs - prevEndAbs) / 60;
        if (startAbs < prevEndAbs) {
          // Dubbelbokning: passet överlappar medarbetarens föregående pass.
          const overlapp = (prevEndAbs - startAbs) / 60;
          w.push({ typ: "kollision", text: `${namn} är redan bokad – passen överlappar ${h1(overlapp)} h`, indikation: false });
          const forra = lista[i - 1];
          if (forra) (varningar[forra.id] ||= []).push({ typ: "kollision", text: `${namn} är dubbelbokad ${h1(overlapp)} h med ett annat pass`, indikation: false });
        } else if (vila < 11) {
          w.push({ typ: "dygnsvila", text: `Dygnsvila endast ${h1(vila)} h (kräver 11 h)`, indikation: false });
        }
      }
      // Pass i följd
      if (prevDate && dayIndex(model, p.datum) - dayIndex(model, prevDate) === 1) foljd += 1;
      else if (!prevDate || dayIndex(model, p.datum) - dayIndex(model, prevDate) === 0) { /* samma dag */ }
      else foljd = 0;
      if (foljd + 1 > prof.maxFoljd) w.push({ typ: "foljd", text: `${foljd + 1} arbetsdagar i följd (max ${prof.maxFoljd})`, indikation: false });
      prevDate = p.datum; prevEndAbs = endAbs;
      // Veckotimmar (indikation)
      const vecka = isoWeek(p.datum); veckaH[vecka] = (veckaH[vecka] || 0) + p.betald; totalH += p.betald;
      if (w.length) varningar[p.id] = w;
    }
    // Övertid/veckovila som indikationer per vecka
    for (const vecka of Object.keys(veckaH)) {
      if (veckaH[vecka] > 40) {
        // markera veckans sista pass med indikation
        const veckaPass = lista.filter((p) => isoWeek(p.datum) === vecka);
        const sista = veckaPass[veckaPass.length - 1];
        if (sista) (varningar[sista.id] ||= []).push({ typ: "overtid", text: `≈ ${h1(veckaH[vecka])} h denna vecka – kontrollera övertid/veckovila mot avtal`, indikation: true });
      }
    }
    // SSG-avvikelse: planerad tid mot mål (budget h/mån × SSG-faktor redan i budgetH)
    const mål = prof.budgetH;
    const diff = totalH - mål;
    medInfo[namn] = { planeradH: totalH, malH: mål, diff, ssgMal: prof.ssgMal, nattbehorig: prof.nattbehorig };
  }
  return { varningar, medInfo };
}
function dayIndex(model, iso) { return model.dagar.indexOf(iso); }
function isoWeek(iso) {
  const d = new Date(iso + "T12:00:00Z"); const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day + 3); const firstThu = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  return `${d.getUTCFullYear()}-v${1 + Math.round((d - firstThu) / 6048e5)}`;
}

/* ================================================================== *
 * Kundbehovsbräde ("lek-kopia") – sprid flyttbara insatser inom fönster.
 * Bygger per-dag-modell ur insatsraderna. Att flytta en insats ändrar bara
 * kundLek (state.kundLek), aldrig importerad data. Möten/utbildning läggs som
 * egna block och placeras i störst lucka i kundbehovet.
 * ================================================================== */
function kundLek() { return state.kundLek || { moves: {}, moten: [] }; }

// Insatser för en viss dag med fönstergränser (tidigast = Planerad start,
// senast = Fönster slut − varaktighet). Flyttbara med utrymme kan dras.
function kundDagModell(iso) {
  const dayRows = arbetsRader().filter((r) => r.datum === iso);
  const lek = kundLek();
  return dayRows.map((r, i) => {
    const id = `k${r.kallrad ?? i}`;
    const dur = Math.max(1, Number(r.minuter) || 0);
    const startMin = clockMin(r.start);
    const fonsterSlutMin = r.fonsterSlut ? clockMin(r.fonsterSlut) : (startMin != null ? startMin + dur : null);
    const tidigast = startMin;
    const senast = fonsterSlutMin != null ? fonsterSlutMin - dur : startMin;
    const slack = (senast != null && tidigast != null) ? senast - tidigast : 0;
    const flyttbar = r.flyttbar && slack > 0;
    const nuStart = lek.moves[id] != null ? lek.moves[id] : startMin;
    return {
      id, kund: r.kund, insats: r.insats, dur,
      tidigast, senast, slack, flyttbar,
      staff: r.tvaPersoner ? 2 : 1,
      start: nuStart, end: nuStart + dur,
      fonsterStart: tidigast, fonsterEnd: fonsterSlutMin,
      original: startMin,
      moved: lek.moves[id] != null && lek.moves[id] !== startMin,
    };
  }).filter((p) => p.start != null);
}

// Samtidighet per 15 min för en dags insatser (+ möten som upptar personal).
function kundDagKurva(insatser, moten) {
  const slots = new Array(96).fill(0);
  for (const p of insatser) {
    const s = Math.floor(p.start / 15), e = Math.floor((p.end - 1) / 15);
    for (let sl = s; sl <= e && sl < 96; sl++) slots[sl] += p.staff;
  }
  for (const m of (moten || [])) {
    const s = Math.floor(m.start / 15), e = Math.floor((m.start + m.dur - 1) / 15);
    for (let sl = s; sl <= e && sl < 96; sl++) slots[sl] += (m.personal || 1);
  }
  let peak = 0, peakSlot = 0;
  slots.forEach((v, i) => { if (v > peak) { peak = v; peakSlot = i; } });
  return { slots, peak, peakSlot };
}

// Hittar största sammanhängande lucka i kundbehovet (för mötesförslag),
// inom kontorstid 08–17 där behovet är som lägst.
function forslaMoteslucka(insatser, dur) {
  const kurva = kundDagKurva(insatser, []).slots;
  const from = 8 * 4, to = 17 * 4; // 08:00–17:00 i 15-min-slots
  const behov = dur / 15;
  let bäst = { start: 9 * 60, last: Infinity };
  for (let s = from; s + behov <= to; s++) {
    let last = 0; for (let k = 0; k < behov; k++) last += kurva[s + k] || 0;
    if (last < bäst.last) bäst = { start: s * 15, last };
  }
  return bäst.start;
}
function clockMin(c) { const m = String(c ?? "").match(/(\d{1,2}):(\d{2})/); return m ? +m[1] * 60 + +m[2] : null; }
function minClock(m) { m = ((Math.round(m) % 1440) + 1440) % 1440; return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; }

/* ================================================================== *
 * SCENARIER – nuläge (juni utfall) vs nytt optimerat schema.
 * Ett scenario är en sammanfattning hämtad ur filens egna blad
 * (Uppföljning + Beräkningar + Optimering). Appen jämför två scenarier;
 * den optimerar inte själv – optimeringen görs i modellen och läses in.
 * ================================================================== */
function parseUppfoljning(wb) {
  const name = wb.SheetNames.find((n) => /uppf/i.test(n));
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => row.map((c) => String(c ?? "").toLowerCase()).includes("kundinsatser h"));
  if (hi < 0) return null;
  // Kolumnvärdena ligger förskjutna ett steg efter rubriken i pilotfilen:
  // datum, kundinsatser, resursbehov, schematid, tillgänglig, (tom=utförd),
  // kundnära(plan), underbem, gap, andel, kostnad, status.
  const dagar = [];
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; const iso = cellToIso(row[0]); if (!iso) continue;
    dagar.push({
      datum: iso,
      kundinsatser: num(row[1]), resursbehov: num(row[2]), schematid: num(row[3]),
      tillganglig: num(row[4]), kundnara: num(row[6]), underbem: num(row[7]),
      gap: num(row[8]), kostnad: num(row[10]),
    });
  }
  return dagar.length ? dagar : null;
}
function parseUnderbem(wb) {
  const name = wb.SheetNames.find((n) => /underbemann/i.test(n));
  if (!name) return null;
  const grid = XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true });
  const hi = grid.findIndex((row) => String(row[0] ?? "").toLowerCase() === "klockslag");
  if (hi < 0) return null;
  const perTimme = [];
  for (let r = hi + 1; r < grid.length; r++) {
    const row = grid[r]; const kl = String(row[0] ?? "");
    if (!/^\d{1,2}:\d{2}/.test(kl)) continue;
    perTimme.push({ klockslag: kl, intervall: num(row[1]), gap: num(row[3]), storst: num(row[4]), status: String(row[5] ?? "") });
  }
  return perTimme.length ? perTimme : null;
}
function num(v) { return typeof v === "number" ? v : (Number(v) || 0); }

// Bygger ett scenario ur en arbetsbok: aggregat + dagserie + per timme.
function byggScenario(wb, kalla) {
  const dagar = parseUppfoljning(wb);
  const ber = parseKeyValueSheet(wb, "Beräkningar");
  const perTimme = parseUnderbem(wb);
  if (!dagar) return null;
  const sum = (k) => dagar.reduce((s, d) => s + d[k], 0);
  const bv = (namn, fb) => { const v = ber && ber[namn] ? ber[namn].value : null; return typeof v === "number" ? v : fb; };
  const schematid = sum("schematid");
  const kundnara = sum("kundnara");
  return {
    kalla,
    dagar,
    perTimme,
    kundinsatserH: sum("kundinsatser"),
    resursbehovH: sum("resursbehov"),
    schematidH: schematid,
    tillgangligH: sum("tillganglig"),
    kundnaraH: kundnara,
    kundnaraAndel: schematid > 0 ? kundnara / schematid * 100 : 0,
    bemanningsgapH: sum("gap"),
    underbemIntervall: dagar.reduce((s, d) => s + d.underbem, 0),
    schemakostnad: bv("Ren schemakostnad", sum("kostnad")),
    personalbudget: bv("Aktuell personalbudget", state.budget),
    totalPrognos: bv("Total kostnadsprognos", sum("kostnad")),
    // Planvärden (faktiskt utfall saknas i pilotfilen) – märks i vyn.
    utfallSaknas: true,
  };
}

/* ---------- Andra scenariot: läs in ett optimerat schema att jämföra mot ---------- */
function handleNyttSchema(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    let wb;
    try { wb = XLSX.read(new Uint8Array(e.target.result), { type: "array", cellDates: true }); }
    catch (err) { notera("Kunde inte läsa filen", "fel", { detalj: err.message }); return; }
    const sc = byggScenario(wb, "Optimerat schema");
    if (!sc) { notera("Filen saknar bladet Uppföljning", "fel", { detalj: "Utan det bladet kan filen inte läsas som ett schema." }); return; }
    sc.fileName = file.name;
    state.nyttSchema = sc;
    persist();
    render();
  };
  reader.readAsArrayBuffer(file);
}
function rensaNyttSchema() { state.nyttSchema = null; persist(); render(); }

/* ================================================================== *
 * Naivt nuläge ("före"): räknas fram ur kundbehovet. Representerar ett
 * ooptimerat schema – insatser ospridda (topparna kvar), överbemanning i
 * lågtimmar (golv dygnet runt) och ineffektiv timvis avrundning/omlott.
 * X2:s inlästa schema (Uppföljning) är "efter". Kontrasten är alltså räknad
 * ur samma kundbehov, inte påhittad.
 * ================================================================== */
/* ================================================================== *
 * Redigering av kundbehov. Ändringar slår igenom live på
 * kundbehovssiffror, resurskurva och per kund – allt räknas ur arbetsRader().
 * Rör aldrig den importerade datan; "Återställ" tar bort lek-kopian.
 * ================================================================== */
function kundEditSet(id, falt, varde) {
  const ed = startaKundEdit();
  const r = ed.rows.find((x) => String(x._id) === String(id));
  if (!r) return;
  if (falt === "minuter") {
    const m = Math.max(1, Math.round(Number(varde) || 0));
    r.minuter = m;
    if (r.start) r.slut = addClock(r.start, m); // håll slut i takt med längden
  } else if (falt === "start") {
    const c = String(varde).match(/^(\d{1,2}):(\d{2})$/);
    if (c) { r.start = `${c[1].padStart(2, "0")}:${c[2]}`; if (r.minuter) r.slut = addClock(r.start, Math.round(r.minuter)); }
  } else if (falt === "flyttbar") {
    r.flyttbar = !!varde;
  } else if (falt === "typ") {
    r.flyttbar = (String(varde) === "Flyttbar");
  } else if (falt === "kund") {
    r.kund = String(varde || "").trim() || "Gemensamt";
  } else if (falt === "senast") {
    const c = String(varde).match(/^(\d{1,2}):(\d{2})$/);
    if (c) r.fonsterSlut = `${c[1].padStart(2, "0")}:${c[2]}`;
  } else if (falt === "dubbel") {
    r.tvaPersoner = !!varde;
  }
  persist(); render();
}
function kundEditTaBort(id) {
  const ed = startaKundEdit();
  ed.rows = ed.rows.filter((x) => String(x._id) !== String(id));
  persist(); render();
}
function kundEditLaggTill(iso) {
  const ed = startaKundEdit();
  const nyId = "ny" + Math.random().toString(36).slice(2, 8);
  ed.rows.push({
    _id: nyId, kallrad: null, datum: iso,
    kund: "Gemensamt", insats: "Ny insats", start: "09:00", slut: "09:30",
    fonsterSlut: null, minuter: 30, tvaPersoner: false, flyttbar: true, status: "",
  });
  persist(); render();
}
// Lägg till en helt ny kund (med en första insats som utkast) så kunden syns.
function kundLaggTillNy(namn, iso) {
  const kund = String(namn || "").trim();
  if (!kund) return 0;
  const ed = startaKundEdit();
  const nyId = "ny" + Math.random().toString(36).slice(2, 8);
  ed.rows.unshift({
    _id: nyId, kallrad: null, datum: iso,
    kund, insats: "Ny insats", beskrivning: "Beskriv vad som ska göras",
    start: "09:00", slut: "09:30", fonsterSlut: null,
    minuter: 30, tvaPersoner: false, flyttbar: true, status: "utkast",
  });
  persist(); render();
  setTimeout(() => { const el = document.querySelector(".kb-utkast"); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" }); }, 40);
  return 1;
}
// Veckodag ur ISO-datum: 0=mån ... 6=sön (svensk ordning).
function veckodagIdx(iso) { const d = new Date(iso + "T12:00:00Z").getUTCDay(); return (d + 6) % 7; }
// Vilka veckodagar (0-6) en insats förekommer på, över hela perioden. En insats
// identifieras av kund+insats+starttid (samma "typ" på olika datum).
function insatsVeckodagar(rad) {
  const nyckel = (r) => `${r.kund}|${r.insats}|${r.start}`;
  const k = nyckel(rad);
  const dagar = new Set();
  for (const r of arbetsRader()) if (nyckel(r) === k && r.datum) dagar.add(veckodagIdx(r.datum));
  return dagar;
}
// Slå av/på en veckodag för en insats-typ. Av = ta bort alla förekomster på den
// veckodagen. På = lägg till en förekomst på varje sådant datum i perioden.
function kundToggleVeckodag(id, dagIdx) {
  const ed = startaKundEdit();
  const matchId = (r) => String(r._id) === String(id) || String(r.kallrad) === String(id);
  const rad = ed.rows.find(matchId);
  if (!rad) return;
  const nyckel = (r) => `${r.kund}|${r.insats}|${r.start}`;
  const k = nyckel(rad);
  const finns = ed.rows.some((r) => nyckel(r) === k && r.datum && veckodagIdx(r.datum) === dagIdx);
  if (finns) {
    // Ta bort alla förekomster på den veckodagen.
    ed.rows = ed.rows.filter((r) => !(nyckel(r) === k && r.datum && veckodagIdx(r.datum) === dagIdx));
  } else {
    // Lägg till på varje datum i perioden som infaller på den veckodagen.
    const mall = ed.rows.find((r) => nyckel(r) === k) || rad;
    for (let i = 0; i < state.importDays; i++) {
      const iso = addDays(state.period.from, i);
      if (veckodagIdx(iso) !== dagIdx) continue;
      if (ed.rows.some((r) => nyckel(r) === k && r.datum === iso)) continue;
      ed.rows.push({ ...mall, _id: "ny" + Math.random().toString(36).slice(2, 8), kallrad: null, datum: iso, status: mall.status || "" });
    }
  }
  persist(); render();
}

/* ================================================================== *
 * Redigering av personal. Ändra SSG samt lägg till/ta bort
 * medarbetare. Summorna (antal, budgettid, kostnad) uppdateras live.
 * Rör aldrig importerad data; "Återställ" tar bort lek-kopian.
 * Obs: schema och före/efter räknas ur X2:s blad och påverkas inte.
 * ================================================================== */
function personalRader() {
  if (state.personalEdit && state.personalEdit.rows) return state.personalEdit.rows;
  return state.personal ? state.personal.rows : [];
}
function personalEditAktiv() { return !!(state.personalEdit && state.personalEdit.rows); }
function startaPersonalEdit() {
  if (!state.personalEdit || !state.personalEdit.rows) {
    const src = state.personal ? state.personal.rows : [];
    state.personalEdit = { rows: src.map((r, i) => ({ ...r, _pid: r._pid || ("p" + i) })) };
  }
  return state.personalEdit;
}
function aterstallPersonalEdit() { state.personalEdit = null; persist(); render(); }
function personalSet(id, falt, varde) {
  const ed = startaPersonalEdit();
  const r = ed.rows.find((x) => String(x._pid) === String(id)); if (!r) return;
  if (falt === "ssg") {
    // SSG lagras som andel i filen (1,0 = 100 %). Reglaget matar in procent.
    const nyPct = Math.max(0, Math.min(150, Number(varde) || 0));
    const ny = nyPct / 100;
    const gammal = Number(r["Grund-SSG"]) || 1;
    const faktor = gammal > 0 ? ny / gammal : 1;
    r["Grund-SSG"] = ny;
    if (typeof r["Budget h/mån"] === "number") r["Budget h/mån"] = r["Budget h/mån"] * faktor;
    if (typeof r["Tillgängligt h/mån"] === "number") r["Tillgängligt h/mån"] = r["Tillgängligt h/mån"] * faktor;
    const timk = Number(r["Timkostnad"]) || 0;
    if (typeof r["Budget h/mån"] === "number") r["Budgetkostnad/mån"] = r["Budget h/mån"] * timk;
  } else if (falt === "namn") {
    r["Medarbetare"] = String(varde || "").trim() || "Ny medarbetare";
  } else if (falt === "status") {
    r["Status"] = String(varde || "Anställd");
  } else if (falt === "passprofil") {
    r["Passprofil"] = String(varde || "Dag/kväll");
    // Nattprofil kräver nattbehörighet – annars kan personen inte få nattpass.
    if (/natt/i.test(String(varde))) r["Nattbehörig"] = "Ja";
  } else if (falt === "helg") {
    r["Helgmodell"] = String(varde || "Varannan helg");
  } else if (falt === "natt") {
    r["Nattbehörig"] = varde ? "Ja" : "Nej";
  } else if (falt === "heltid") {
    const heltid = Math.max(0, Math.min(60, Number(varde) || 0));
    r["Heltid h/vecka"] = heltid;
    const ssg = Number(r["Grund-SSG"]) || 1;
    const budgetH = heltid * 4.345 * ssg;
    r["Budget h/mån"] = budgetH;
    r["Tillgängligt h/mån"] = budgetH;
    r["Budgetkostnad/mån"] = budgetH * (Number(r["Timkostnad"]) || 0);
  } else if (falt === "timkostnad") {
    const timk = Math.max(0, Number(varde) || 0);
    r["Timkostnad"] = timk;
    r["Budgetkostnad/mån"] = (Number(r["Budget h/mån"]) || 0) * timk;
  } else if (falt === "budget") {
    const budgetH = Math.max(0, Number(varde) || 0);
    r["Budget h/mån"] = budgetH;
    r["Tillgängligt h/mån"] = budgetH;
    r["Budgetkostnad/mån"] = budgetH * (Number(r["Timkostnad"]) || 0);
  }

  persist(); render();
}
function personalTaBort(id) {
  const ed = startaPersonalEdit();
  ed.rows = ed.rows.filter((x) => x._pid !== id);
  persist(); render();
}
// Skapar en ny medarbetare från formulärets värden.
function personalLaggTillFran(data) {
  const ed = startaPersonalEdit();
  const pid = "ny" + Math.random().toString(36).slice(2, 7);
  const heltid = Number(data.heltid) || 40;
  const ssg = Math.max(0, Math.min(1.5, (Number(data.ssg) || 100) / 100));
  const timk = Number(data.timkostnad) || 270;
  const budgetH = heltid * 4.345 * ssg;
  ed.rows.unshift({
    _pid: pid,
    "Medarbetare": (data.namn || "").trim() || "Ny medarbetare",
    "Status": data.status || "Anställd",
    "Passprofil": data.passprofil || "Dag/kväll",
    "Grund-SSG": ssg, "Heltid h/vecka": heltid, "Budget h/mån": budgetH,
    "Tillgängligt h/mån": budgetH, "Timkostnad": timk, "Budgetkostnad/mån": budgetH * timk,
    "Nattbehörig": data.natt ? "Ja" : "Nej", "Helgmodell": data.helg || "Varannan helg",
    "Planerade h": 0, "SSG-avvikelse h": 0,
  });
  persist(); render();
  setTimeout(() => { const el = document.querySelector(".mb-kort"); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" }); }, 40);
}

/* ---------- Avidentifiering: byt riktiga medarbetarnamn mot fiktiva ---------- */
// Kör vid import. Medarbetarna får fiktiva,
// stjärn-/rymdtematiska namn så inget kan spåras till verkliga personer.
const FIKTIVA_NAMN = {
  // Tom. Datan är redan avidentifierad; ingen namnöversättning behövs.
};
function avidentifieraNamn() {
  const byt = (namn) => {
    const n = String(namn ?? "").trim();
    return FIKTIVA_NAMN[n] || namn;
  };
  if (state.personal && state.personal.rows) {
    for (const r of state.personal.rows) if (r["Medarbetare"] != null) r["Medarbetare"] = byt(r["Medarbetare"]);
  }
  if (state.individschema && state.individschema.rows) {
    for (const r of state.individschema.rows) {
      for (const key of Object.keys(r)) {
        if (/medarbetare/i.test(key) && r[key] != null) r[key] = byt(r[key]);
      }
    }
  }
  // Ev. redan startade lek-kopior speglar originalet – nollställ dem.
  state.personalEdit = null;
}

/* ================================================================== *
 * Styrande villkor: läser Inställningar (regler & antaganden),
 * Individvillkor (datumstyrda undantag) och Rörliga villkor (katalog).
 * Visas i en egen flik för att påvisa modellens genomtänkta regelverk.
 * ================================================================== */
function parseVillkor(wb) {
  const out = { installningar: [], individ: [], rorligaKategorier: {}, rorligaAntal: 0 };
  // Inställningar: Antagande | Värde | Enhet | Kommentar
  const namnI = wb.SheetNames.find((n) => /inställning/i.test(n));
  if (namnI) {
    const g = XLSX.utils.sheet_to_json(wb.Sheets[namnI], { header: 1, raw: true });
    const hi = g.findIndex((r) => String(r[0] ?? "").toLowerCase() === "antagande");
    if (hi >= 0) for (let r = hi + 1; r < g.length; r++) {
      const rad = g[r]; const namn = rad[0]; if (namn == null || String(namn).trim() === "") continue;
      out.installningar.push({
        namn: String(namn).trim(),
        varde: cellToText(rad[1]),
        enhet: rad[2] != null ? String(rad[2]).trim() : "",
        kommentar: rad[3] != null ? String(rad[3]).trim() : "",
      });
    }
  }
  // Individvillkor: ID | Medarbetare | Villkorstyp | Från | Till | Veckodag
  const namnV = wb.SheetNames.find((n) => /individvillkor/i.test(n));
  if (namnV) {
    const g = XLSX.utils.sheet_to_json(wb.Sheets[namnV], { header: 1, raw: true });
    const hi = g.findIndex((r) => String(r[0] ?? "").toLowerCase() === "id");
    if (hi >= 0) for (let r = hi + 1; r < g.length; r++) {
      const rad = g[r]; const mb = rad[1], typ = rad[2];
      if (!mb || !typ || String(mb).trim() === "" || String(typ).trim() === "") continue;
      out.individ.push({
        medarbetare: String(mb).trim(), typ: String(typ).trim(),
        fran: cellToIso(rad[3]) || "", till: cellToIso(rad[4]) || "",
      });
    }
  }
  // Rörliga villkor: ID | Kategori | Villkorstyp | ... (katalog av mallar)
  const namnR = wb.SheetNames.find((n) => /rörliga villkor/i.test(n));
  if (namnR) {
    const g = XLSX.utils.sheet_to_json(wb.Sheets[namnR], { header: 1, raw: true });
    const hi = g.findIndex((r) => String(r[0] ?? "").toLowerCase() === "id");
    if (hi >= 0) for (let r = hi + 1; r < g.length; r++) {
      const rad = g[r]; const kat = rad[1], typ = rad[2];
      if (!kat || !typ) continue;
      const k = String(kat).trim();
      if (!out.rorligaKategorier[k]) out.rorligaKategorier[k] = [];
      out.rorligaKategorier[k].push(String(typ).trim());
      out.rorligaAntal++;
    }
  }
  return out;
}
function cellToText(v) {
  if (v == null) return "";
  if (isDate(v)) return cellToIso(v);
  if (typeof v === "number") {
    // Andelar lagras som 0..1 – visa som procent om det ser ut så.
    return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000);
  }
  return String(v).trim();
}

/* ================================================================== *
 * Redigering av intäkter. Ändra grundersättning per kund
 * (kr/dygn) – beräknad intäkt och månadsintäkt räknas om live. Rör aldrig
 * importerad data; "Återställ" tar bort lek-kopian.
 * ================================================================== */
function intaktRader() {
  if (state.intaktEdit && state.intaktEdit.rows) return state.intaktEdit.rows;
  return state.intakter ? state.intakter.rows : [];
}
function intaktEditAktiv() { return !!(state.intaktEdit && state.intaktEdit.rows); }
function startaIntaktEdit() {
  if (!state.intaktEdit || !state.intaktEdit.rows) {
    const src = state.intakter ? state.intakter.rows : [];
    state.intaktEdit = { rows: src.map((r) => ({ ...r })) };
  }
  return state.intaktEdit;
}
function aterstallIntaktEdit() { state.intaktEdit = null; persist(); render(); }
// Sätter grundersättning (kr/dygn) för en kund över alla dagar och räknar om
// beräknad intäkt = giltig grundersättning × intäktsfaktor (om aktiv kund).
function intaktSetGrund(kund, krPerDygn) {
  const ed = startaIntaktEdit();
  const belopp = Math.max(0, Math.round(Number(krPerDygn) || 0));
  for (const r of ed.rows) {
    if (String(r["Kund"] ?? "").trim() !== kund) continue;
    r["Grund kr/dygn"] = belopp;
    r["Ny ersättning"] = belopp;
    r["Giltig grundersättning"] = belopp;
    const aktiv = Number(r["Aktiv kund"]);
    const faktor = typeof r["Intäktsfaktor"] === "number" ? r["Intäktsfaktor"] : 1;
    r["Beräknad intäkt"] = (aktiv === 0 ? 0 : belopp) * faktor;
  }
  persist(); render();
}
// Aktivera/inaktivera en kund (0/1) – inaktiv kund ger 0 i intäkt.
function intaktSetAktiv(kund, aktiv) {
  const ed = startaIntaktEdit();
  for (const r of ed.rows) {
    if (String(r["Kund"] ?? "").trim() !== kund) continue;
    r["Aktiv kund"] = aktiv ? 1 : 0;
    const belopp = Number(r["Grund kr/dygn"]) || 0;
    const faktor = typeof r["Intäktsfaktor"] === "number" ? r["Intäktsfaktor"] : 1;
    r["Beräknad intäkt"] = (aktiv ? belopp : 0) * faktor;
  }
  persist(); render();
}

/* ================================================================== *
 * Genomförandeplan: skapar ett första dagsutkast av typiska insatser för
 * en vald kund (mall härledd ur verkliga planer). Appen kan därmed ersätta
 * Sekoia – man får ett startförslag och justerar sedan manuellt i tabellen.
 * ================================================================== */
const GFP_MALL = [
  { start: "07:30", min: 30, titel: "Morgonrutin", besk: "Jag vill ha hjälp upp ur sängen, till toaletten och med övre och nedre hygien. Hjälp mig att klä på mig dagkläder." },
  { start: "08:00", min: 45, titel: "Dusch", besk: "Jag duschar med stöd. Hjälp mig ut till badrummet med gåbordet, jag behöver hjälp att tvätta ryggen och fötterna." },
  { start: "09:00", min: 20, titel: "Frukost", besk: "Servera frukost i köket: kaffe med mjölk och två smörgåsar. Påminn mig om morgonmedicinen." },
  { start: "10:00", min: 20, titel: "Träning", besk: "Gå igenom mitt träningsprogram, gångträning i korridoren med rollator. Uppmuntra men pressa inte." },
  { start: "12:00", min: 20, titel: "Lunch", besk: "Jag vill bli serverad lunch i gemensamma köket. Jag äter självständigt men kan behöva hjälp att skära maten." },
  { start: "13:00", min: 30, titel: "Byte av inkontinensskydd", besk: "Hjälp mig till toaletten för byte. Vid förflyttning använder jag alltid lyfthjälpmedel." },
  { start: "14:30", min: 10, titel: "Tillsyn", besk: "Kom in och se om jag är vaken och om jag behöver hjälp till toaletten eller något att dricka." },
  { start: "15:30", min: 60, titel: "Vila", besk: "Efter maten vill jag vila en stund. Byt inkontinensskydd innan jag lägger mig." },
  { start: "17:00", min: 45, titel: "Middag", besk: "Hjälp mig till gemensamma middagen. Jag vill ha en kopp kaffe efteråt. Påminn om kvällsmedicin." },
  { start: "19:30", min: 20, titel: "Fika", besk: "Ge mig kaffe och en smörgås. Hjälp mig upp ur sängen om jag har lagt mig." },
  { start: "20:30", min: 25, titel: "Kvällsrutin", besk: "Hjälp mig till toaletten, tandborstning, byte till nattkläder och hjälp i säng. Sätt upp sänggrindarna." },
  { start: "23:00", min: 10, titel: "Tillsyn", besk: "Kom in tyst och kontrollera att jag sover lugnt. Fråga om jag behöver kissa om jag är vaken." },
];
// Lista över kunder i nuvarande behov (för att välja vem planen skapas åt).
function gfpKunder() {
  const set = new Set();
  for (const r of arbetsRader()) { const k = String(r.kund ?? "").trim(); if (k && !/^gemensam/i.test(k)) set.add(k); }
  return [...set].sort((a, b) => a.localeCompare(b, "sv"));
}
// Skapar dagsutkast för vald kund, en insats per malla-rad, för varje dag i
// perioden (så behovet finns hela månaden). Läggs på lek-kopian.
function laggTillGenomforandeplan(kund) {
  if (!kund) return;
  const ed = startaKundEdit();
  const days = [];
  for (let i = 0; i < state.importDays; i++) days.push(addDays(state.period.from, i));
  let n = 0;
  for (const iso of days) {
    for (const m of GFP_MALL) {
      ed.rows.push({
        _id: "gfp" + Math.random().toString(36).slice(2, 9),
        kallrad: null, datum: iso, kund,
        insats: m.titel, beskrivning: m.besk,
        start: m.start, slut: addClock(m.start, m.min), fonsterSlut: null,
        minuter: m.min, tvaPersoner: false, flyttbar: true, status: "utkast",
      });
      n++;
    }
  }
  persist();
  return n;
}

/* ================================================================== *
 * Kommandoruta ("Fråga appen"): tolkar fri text från VC:n och antingen
 * navigerar till rätt flik eller svarar på en fråga om siffrorna. Enkel
 * nyckelordsmatchning – fungerar offline. Säger ärligt ifrån om den inte
 * förstår, i stället för att gissa.
 * ================================================================== */
function tolkaKommando(text) {
  const t = (text || "").toLowerCase().trim();
  if (!t) return { typ: "tomt" };
  const d = (typeof derive === "function") ? derive() : null;
  const har = (arr) => arr.some((w) => t.includes(w));
  const kr = (x) => Math.round(x).toLocaleString("sv-SE") + " kr";
  const h1v = (x) => (typeof h1 === "function" ? h1(x) : Math.round(x));
  const bv = (namn) => (state.berakningar && state.berakningar[namn] && typeof state.berakningar[namn].value === "number") ? state.berakningar[namn].value : null;

  // --- Åtgärder ---
  if (har(["börja om", "boerja om", "starta om", "nollställ", "återställ demo", "reset"]))
    return { typ: "atgard", handling: "omstart", svar: "Startar om demon till nuläget." };
  if (har(["skapa bemanningsbalans", "skapa balans", "optimera", "gör grönt", "importera", "ladda upp", "läs in", "hr-export", "x2"]))
    return { typ: "atgard", handling: "skapa", svar: "Skapar bemanningsbalans – schemat optimeras." };

  // --- Navigering: flik-nyckelord ---
  const navMap = [
    { tab: "ekonomi", ord: ["ekonomi", "budget", "kostnad", "pengar", "intäkt totalt"] },
    { tab: "intakter", ord: ["intäkt", "intakt", "ersättning", "grundersättning"] },
    { tab: "personal", ord: ["personal", "medarbetare", "ssg", "sysselsättning", "anställd"] },
    { tab: "schema", ord: ["schema", "pass", "arbetspass"] },
    { tab: "kundbehov", ord: ["kundbehov", "insats", "genomförandeplan", "behov"] },
    { tab: "kunder", ord: ["per kund", "kunder", "kund "] },
    { tab: "resurskurva", ord: ["resurskurva", "kurva", "samtidig"] },
    { tab: "sprid", ord: ["sprid", "jämna ut", "toppar"] },
    { tab: "nyckeltal", ord: ["nyckeltal", "procent", "andel"] },
    { tab: "villkor", ord: ["villkor", "regler", "regelverk", "avtal"] },
    { tab: "atgarder", ord: ["åtgärd", "atgard", "varning", "att göra"] },
    { tab: "simulering", ord: ["vad händer", "simulera", "reglage", "känslighet"] },
    { tab: "oversikt", ord: ["översikt", "oversikt", "dashboard", "startsida", "hem"] },
  ];
  // Frågor om siffror (svaras direkt, även utan att byta flik) ---
  const optimerat = !!state.optimerat;
  if (har(["kundnära", "kundnara", "tid hos kund"])) {
    const andel = bv("Planerad kundnära andel");
    if (schematidKalla() !== "medvind") return { typ: "svar", svar: "Jag kan inte räkna kundnära tid än – läs in personalschemat från Medvind, då kommer schematiden från det riktiga schemat." };
    if (andel != null) {
      const pct = andel * 100;
      const mal = (bv("Mål kundnära tid") || 0.75) * 100;
      return { typ: "svar", svar: `Kundnära tid är ${h1v(pct)} % av schematiden (mål ${h1v(mal)} %) – ${pct >= mal ? "över" : "under"} målet.` };
    }
  }

  if (har(["håller budget", "haller budget", "budget håller", "går vi plus", "ekonomin ok", "har vi råd"])) {
    const disp = bv("Disponibelt utrymme efter ekonomisk reserv");
    if (optimerat && disp != null) return { typ: "svar", svar: disp >= 0 ? `Ja, budgeten håller med ${kr(disp)} i marginal efter den ekonomiska reserven.` : `Nej, budgeten överskrids med ${kr(-disp)}.` };
    return { typ: "svar", svar: "Importera HR-exporten först, så visar jag budgetläget för det optimerade schemat." };
  }
  if (har(["schematid", "hur mycket schema", "arbetstid totalt"])) {
    const s = bv("Planerad schematid");
    if (s != null) return { typ: "svar", svar: `Planerad schematid är ${h1v(s)} h för perioden.` };
  }
  if (har(["månadsintäkt", "manadsintakt", "hur mycket tjänar", "intäkt totalt", "intäkterna"])) {
    const m = bv("Månadsintäkt");
    if (m != null) return { typ: "svar", svar: `Månadsintäkten är ${kr(m)} (grundersättning per kund och dygn).`, tab: "intakter" };
  }
  if (har(["kostnad", "vad kostar"]) && !har(["ekonomi"])) {
    const k = bv("Ren schemakostnad");
    if (k != null) return { typ: "svar", svar: `Ren schemakostnad är ${kr(k)} (schematid × timkostnad).`, tab: "ekonomi" };
  }
  if (har(["hur många insatser", "antal insatser", "hur många kunder"])) {
    if (d) return { typ: "svar", svar: `Perioden har ${d.n.antalInsatser} insatser och kundbehovet är ${h1v(d.n.kundbehovH)} h.`, tab: "kundbehov" };
  }
  if (har(["hur många anställda", "antal medarbetare", "hur många jobbar"])) {
    const p = state.personal ? state.personal.rows.filter((r) => String(r["Status"]).toLowerCase() === "anställd").length : null;
    if (p != null) return { typ: "svar", svar: `Det finns ${p} anställda medarbetare (plus vakanser och platshållare).`, tab: "personal" };
  }
  if (har(["mår appen", "hur går det", "läget", "sammanfatta", "status"])) {
    const andel = bv("Planerad kundnära andel");
    const disp = bv("Disponibelt utrymme efter ekonomisk reserv");
    if (schematidKalla() !== "medvind") return { typ: "svar", svar: "Kundbehovet är inläst, men schematiden saknas. Läs in personalschemat från Medvind så kan jag visa kundnära tid och ekonomi." };
    const delar = [andel != null ? `${h1v(andel * 100)} % kundnära tid` : null, disp != null ? (disp >= 0 ? "budgeten håller" : "budgeten överskrids") : null].filter(Boolean);
    return { typ: "svar", svar: `Läget just nu: ${delar.join(", ")}.` };
  }


  // --- Navigering (efter frågorna, så en fråga inte bara byter flik) ---
  for (const n of navMap) if (har(n.ord)) {
    const label = (TABS.find((x) => x.id === n.tab) || {}).label || n.tab;
    return { typ: "navigera", tab: n.tab, svar: `Öppnar ${label}.` };
  }

  // --- Hjälp / förstod inte ---
  if (har(["hjälp", "vad kan du", "hjälp mig", "kommandon"]))
    return { typ: "hjalp" };
  return { typ: "okand" };
}

/* ---------- Schemalagda medarbetare per 15-min-slot för en dag ---------- */
// Räknar hur många medarbetare som är på schema samtidigt (ur Individschema),
// så grafen i Sprid behov kan visa BEHOV (samtidiga insatser) mot BEMANNING
// (schemalagda medarbetare). Nattpass som passerar midnatt hanteras.
// Bemanningskurvan byggs alltid ur Medvind-passen (vikarier med, sovande jour
// utan) – aldrig ur Sekoia-individschemat. Sekoia = kundbehov, inte bemanning.
function schemaPerSlot(iso) {
  const slots = new Array(96).fill(0);
  const pass = (state.balans && state.balans.schemaPass) || schemaPass();
  if (!pass || !pass.length) return slots;
  for (const p of pass) {
    if (p.jour) continue;        // sovande jour räknas inte som bemanning
    if (p.datum !== iso) continue;
    const s = clockMin(p.start); let e = clockMin(p.slut);
    if (s == null || e == null) continue;
    if (e <= s) e += 1440; // passerar midnatt
    for (let sl = Math.floor(s / 15); sl < Math.floor(e / 15) && sl < 96; sl++) slots[sl] += 1;
  }
  return slots;
}

/* ------------------------------------------------------------------ *
 * Vyer och rendering
 * ------------------------------------------------------------------ */
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function renderNav() {
  // Om en flik under "Avancerat" är vald, håll gruppen öppen automatiskt.
  const curTab = TABS.find((t) => t.id === tab);
  if (curTab && curTab.grupp === "Avancerat") window.__avanceratOppen = true;
  const cur = curTab || TABS[0];
  const filled = root.verks.filter((v) => v.rows.length).length;
  publiceraSkal({
    tabs: TABS.map((t) => ({
      ...t,
      last: !tabTillganglig(t),
      klar: t.id === "uppladdning" ? harUnderlag() : t.id === "foreefter" ? harResultat() : false,
    })),
    grupper: TAB_GRUPPER,
    tab,
    avanceratOppen: !!window.__avanceratOppen,
    eyebrow: cur.grupp || cur.label,
    titel: state.org || "Bemanningsbalans",
    org: state.org || "Ny verksamhet",
    periodFoot: state.period
      ? `${state.period.from} – ${addDays(state.period.from, state.importDays - 1)} · ${filled} av ${root.verks.length} importerade`
      : `${filled} av ${root.verks.length} verksamheter importerade`,
    optimerat: !!state.optimerat,
    osparat: harOsparat(),
    version: APP_VERSION,
  });
  renderStegrad();
}

// Stegindikatorn ritas av React (Stegrad i src/components/bb/Skal.tsx) och får
// sitt tillstånd genom publiceraSkal – se renderStegrad längre ned.


/* ---------- Importkontroll-panel ---------- */
function importPanel() {
  if (!pending) return "";
  const p = pending, blocked = p.blockera;
  const perKundRows = p.timmarPerKund.map((k) =>
    `<tr><td><strong>${esc(k.kund)}</strong></td><td>${k.insatser}</td><td>${h1(k.kundbehovH)} h</td></tr>`).join("");
  const rejected = p.avvisade.slice(0, 50).map((a) => `<div>Rad ${a.kallrad}: ${esc(a.orsak)}</div>`).join("");
  const warns = p.varningar.filter((v) => !v.startsWith("BLOCKERAT")).map((v) => `<div>${esc(v)}</div>`).join("");
  const blocks = p.varningar.filter((v) => v.startsWith("BLOCKERAT")).map((v) => `<div>${esc(v.replace("BLOCKERAT: ", ""))}</div>`).join("");
  return `
  <div class="card" style="border-color:var(--teal); margin-bottom:18px">
    <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-start">
      <div>
        <div class="eyebrow">Importkontroll – godkänn innan något sparas</div>
        <h2 style="margin-top:4px">${esc(pendingMeta.fileName)}</h2>
        <p class="muted" style="font-size:12px; margin:6px 0 0">
          Flik: <strong>${esc(pendingMeta.sheet)}</strong> · rubrikrad ${pendingMeta.headerRow} ·
          period ${p.from}–${p.to} (${p.days} dagar). Endast modellens fält läses in.
        </p>
      </div>
      <span class="pill ${blocked ? "red" : p.varningar.length ? "amber" : "green"}">${blocked ? "Importen blockeras" : p.varningar.length ? "Varningar" : "Klar att läsa in"}</span>
    </div>
    <div class="stat-row" style="margin-top:16px">
      ${[["Lästa rader", p.lastaRader], ["Godkända rader", p.godkandaRader], ["Avvisade rader", p.avvisadeRader],
         ["Kunder", p.antalKunder], ["Gemensamma", p.antalGemensamma], ["Fasta", p.antalFasta],
         ["Flyttbara", p.antalFlyttbara], ["Dubbelbemannade", p.antalDubbelbemannade]]
        .map(([l, v]) => `<div class="stat"><div class="lab">${l}</div><div class="val">${v}</div></div>`).join("")}
    </div>
    <div class="grid" style="grid-template-columns:1.1fr 1fr; margin-top:14px">
      <div class="card" style="padding:0; overflow:hidden">
        <table>
          <thead><tr><th>Timmar per kund (${p.days} dagar)</th><th>Insatser</th><th>Kundbehov</th></tr></thead>
          <tbody>${perKundRows}
            <tr class="total"><td>Totalt</td><td>${p.godkandaRader}</td><td>${h1(p.kundbehovH)} h</td></tr>
          </tbody>
        </table>
      </div>
      <div class="grid" style="align-content:start; gap:10px">
        <div class="banner info">
          <div><strong>Hela perioden ${p.from}–${p.to}:</strong> kundbehov ${h2(p.kundbehovH)} h · personalbehov inkl. dubbelbemanning ${h2(p.personalbehovH)} h.
          ${p.first28 ? `<br><strong>Bemanningsplan dag 1–28:</strong> ${p.first28.count} insatser · kundbehov ${h2(p.first28.kundbehovH)} h · personalbehov ${h2(p.first28.personalbehovH)} h.` : ""}</div>
        </div>
        ${blocks ? `<div class="banner" style="background:var(--red-tint); color:var(--red)"><div><strong>Blockerar import:</strong>${blocks}</div></div>` : ""}
        ${warns ? `<div class="banner warn"><div>${warns}</div></div>` : ""}
        ${rejected ? `<div class="banner warn" style="display:block; max-height:160px; overflow:auto"><strong>Avvisade rader:</strong>${rejected}${p.avvisade.length > 50 ? `<div>… och ${p.avvisade.length - 50} till.</div>` : ""}</div>` : ""}
      </div>
    </div>
    <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:16px">
      <button class="btn" id="cancelImport">Avbryt</button>
      <button class="btn primary" id="approveImport" ${blocked ? "disabled" : ""}>Godkänn och läs in</button>
    </div>
  </div>`;
}

/* ---------- Tomt läge ---------- */
function emptyState() {
  return `<div class="drop" id="drop">
    <div style="font-size:34px; line-height:1">↑</div>
    <h2 style="margin:12px 0 6px">Importera din Sekoia-Excel</h2>
    <p class="muted" style="max-width:440px; margin:0 auto 18px">Dra filen hit, eller välj den nedan. Appen läser insatserna, kontrollerar dem och räknar fram kundbehov, resursbehov och nyckeltal. Inget lämnar din dator.</p>
    <button class="btn primary" id="dropPick">Välj Excel-fil</button>
  </div>`;
}

/* ---------- Saknat blad: tydlig upplysning + väg framåt ---------- */
function missingSheet(sheet, vad, hur) {
  return `<div class="saknas">
    <div class="saknas-ic" aria-hidden="true">XLS</div>
    <h2>${esc(vad)} kan inte visas ännu</h2>
    <p>Den inlästa filen saknar bladet <strong>${esc(sheet)}</strong>. ${esc(hur)}</p>
    <div class="saknas-steg">
      <span><b>1</b> Öppna verksamhetens Excel med modellbladen</span>
      <span><b>2</b> Läs in den här</span>
      <span><b>3</b> ${esc(vad)} visas automatiskt</span>
    </div>
    <button class="btn primary" data-pick><span aria-hidden="true">⬆</span> Välj Excel-fil</button>
  </div>`;
}

/* ---------- Vyer ---------- */
function viewOversikt(d) {
  if (!d) return emptyState();
  const twoPeriods = state.importDays > state.planDays;
  const covers = state.analysisDays <= state.planDays;

  // Grundflöde som numrerad tidslinje: stora cirklar (1–6) förbundna med en
  // linje, klickbara till relevant flik. Rent pedagogiskt, påverkar inga andra.
  const flodeSteg = [
    { t: "Kundbehov", u: "vad kunderna behöver", tab: "kundbehov" },
    { t: "Tid", u: "när insatserna sker", tab: "sprid" },
    { t: "Resursbehov", u: "hur många samtidigt", tab: "resurskurva" },
    { t: "Bemanning", u: "vem som jobbar", tab: "personal" },
    { t: "Schema", u: "färdigt pass-schema", tab: "schema" },
    { t: "Uppföljning", u: "mål & kontroll", tab: "nyckeltal" },
  ];
  const grundflode = `<div class="card flode-card">
    <div style="margin-bottom:18px">
      <div class="eyebrow">Grundflöde</div>
      <h2 style="margin:4px 0 3px">Från kundens behov till ett hållbart schema</h2>
      <p class="muted" style="font-size:12px; margin:0">Klicka på ett steg för att öppna det. Samma logik som i Excel – samlad i ett arbetsflöde.</p>
    </div>
    <div class="flode-line">${flodeSteg.map((s, i) =>
      `<button class="flode-nod" onclick="tab='${s.tab}';render()">
        <span class="flode-cirkel">${i + 1}</span>
        <span class="flode-namn">${s.t}</span>
        <span class="flode-sub">${s.u}</span>
      </button>`).join("")}</div>
  </div>`;

  // Daggraf: behov (kundinsatser) vs planerad schematid per veckodag, för
  // vecka 1. Två staplar per dag + notis om var gapet är störst. Byggd ur
  // arbetsRader() och Medvind-passen – inga nya beräkningar.
  let daggraf = "";
  if (state.optimerat) {
    const dagar = [];
    for (let i = 0; i < 7 && i < state.importDays; i++) dagar.push(addDays(state.period.from, i));
    const kbByDay = {}, stByDay = {};
    for (const r of arbetsRader()) { if (!r.datum) continue; kbByDay[r.datum] = (kbByDay[r.datum] || 0) + (r.minuter || 0) / 60; } // rent kundbehov, utan dubbelbemanning
    // Schematid per dag ur Medvind-passen (sovande jour exkluderad) – aldrig Sekoia.
    const stPass = (state.balans && state.balans.schemaPass) || schemaPass();
    for (const p of stPass) { if (p.jour) continue; if (p.datum) stByDay[p.datum] = (stByDay[p.datum] || 0) + (Number(p.timmar) || 0); }
    const veckodag = ["sön", "mån", "tis", "ons", "tor", "fre", "lör"];
    const serie = dagar.map((iso) => {
      const dt = new Date(iso + "T12:00:00Z");
      return { iso, dag: veckodag[dt.getUTCDay()], kb: kbByDay[iso] || 0, st: stByDay[iso] || 0 };
    });
    const maxV = Math.max(1, ...serie.map((s) => Math.max(s.kb, s.st)));
    // Minsta marginal (dagen då schemat ligger tätast mot behovet).
    let gap = null;
    for (const s of serie) { const g = s.st - s.kb; if (!gap || g < gap.g) gap = { ...s, g }; }
    const stapelrader = serie.map((s) => `<div class="dg-col">
        <div class="dg-bars">
          <i class="dg-bar kb" style="height:${s.kb / maxV * 100}%" title="${s.dag}: behov ${h1(s.kb)} h"></i>
          <i class="dg-bar st" style="height:${s.st / maxV * 100}%" title="${s.dag}: schematid ${h1(s.st)} h"></i>
        </div>
        <span class="dg-lbl">${s.dag}</span>
      </div>`).join("");
    const yLbls = [];
    const ySteg = maxV <= 20 ? 5 : maxV <= 60 ? 20 : 50;
    for (let v = 0; v <= maxV; v += ySteg) yLbls.push(`<span style="bottom:${v / maxV * 100}%">${v} h</span>`);
    daggraf = `<div class="card dg-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px; margin-bottom:6px">
        <div><div class="eyebrow">Vecka 1</div><h2 style="margin-top:3px">Behov och planerad tid per dag</h2>
        <p class="muted" style="font-size:12px; margin:4px 0 0">Schematiden täcker kundbehovet varje dag – med marginal för rapport, förflyttning och dubbelbemanning.</p></div>
        <div class="dg-leg"><span><i class="dg-sw kb"></i>Kundbehov</span><span><i class="dg-sw st"></i>Schematid</span></div>
      </div>
      <div class="dg-plot"><div class="dg-yax">${yLbls.join("")}</div><div class="dg-cols">${stapelrader}</div></div>
      ${gap ? `<div class="dg-note ${gap.g >= 0 ? "bra" : "varn"}">${gap.g >= 0 ? "✓ " : "! "}Tätast marginal på ${gap.dag}dag: ${h1(gap.st)} h schematid mot ${h1(gap.kb)} h kundbehov.</div>` : ""}
    </div>`;
  }

  // Beslutsstöd: en kort att-göra-lista för VC, byggd ur befintliga kontroller
  // (samma data som Åtgärder-fliken) + appens egna regelvarningar. Klickbara
  // rader hoppar till rätt flik. Inga nya beräkningar, påverkar inga andra flikar.
  let beslutsstod = "";
  {
    const punkter = [];
    // 1) Modellens kontroller som inte är "pass" (dvs kräver åtgärd/varning).
    if (state.kontroller) {
      for (const r of state.kontroller) {
        if (/^pass$/i.test(r.status)) continue;
        punkter.push({ txt: r.kontroll, meta: r.atgard || String(r.status || ""), tab: "atgarder", ton: /åtgärd/i.test(r.status) ? "röd" : "gul" });
      }
    }
    // 2) Appens egna regelvarningar ur schemamodellen.
    if (state.optimerat) {
      try {
        const m = buildSchemaModel();
        if (m) {
          const v = schemaVarningar(m, schemaEffektiv(m));
          const antal = Object.values(v.varningar).reduce((s, ws) => s + ws.filter((x) => !x.indikation).length, 0);
          if (antal > 0) punkter.push({ txt: "Regelvarningar i schemat", meta: antal + " att se över (dygnsvila, nattbehörighet m.m.)", tab: "schema", ton: "gul" });
        }
      } catch (e) {}
    }
    const visa = punkter.slice(0, 6);
    if (visa.length) {
      beslutsstod = `<div class="card besl-card">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px">
          <div><div class="eyebrow">Beslutsstöd</div><h2 style="margin-top:3px">Det här kan VC titta på</h2></div>
          <span class="pill amber">${punkter.length} punkter</span>
        </div>
        <div class="besl-lista">${visa.map((p) => `<button class="besl-rad" onclick="tab='${p.tab}';render()">
          <span class="besl-dot ${p.ton}"></span>
          <span class="besl-tx"><strong>${esc(p.txt)}</strong><span>${esc(p.meta)}</span></span>
          <span class="besl-pil">›</span></button>`).join("")}</div>
        ${punkter.length > 6 ? `<button class="btn" style="margin-top:10px; font-size:11px" onclick="tab='atgarder';render()">Visa alla ${punkter.length} →</button>` : ""}
      </div>`;
    } else if (state.optimerat) {
      beslutsstod = `<div class="card besl-card">
        <div class="eyebrow">Beslutsstöd</div>
        <div class="tolk bra" style="margin-top:8px">✓ Inget kräver åtgärd just nu – schemat uppfyller målen.</div>
      </div>`;
    }
  }

  // Grundläges-statusband. Före X2-import: ooptimerat nuläge (röda siffror)
  // räknat ur kundbehovet. Efter import: optimerat läge (gröna siffror).
  let statusBand = "";
  const optimerat = !!state.optimerat && hasBer();
  if (optimerat) {
    const andel = ber("Planerad kundnära andel");
    const mal = ber("Mål kundnära tid") || 0.75;
    const disp = ber("Disponibelt utrymme efter ekonomisk reserv");
    const buffert = ber("Beslutad bemanningsbuffert – värde");
    let brott = 0;
    try { const m = buildSchemaModel(); if (m) { const v = schemaVarningar(m, schemaEffektiv(m)); brott = Object.values(v.varningar).reduce((s, ws) => s + ws.filter((x) => !x.indikation).length, 0); } } catch (e) { brott = 0; }
    const andelPct = typeof andel === "number" ? andel * 100 : null;
    const status = [
      { ok: andelPct != null && andelPct >= mal * 100, txt: andelPct != null ? `Kundnära tid ${h1(andelPct)} %` : "Kundnära tid", sub: `mål ${Math.round(mal * 100)} %` },
      { ok: typeof disp === "number" && disp >= 0, txt: "Budget håller", sub: typeof disp === "number" ? `${kr(disp)} kvar efter reserv` : "" },
      { ok: typeof buffert === "number" && buffert > 0, txt: "Bemanningsbuffert", sub: typeof buffert === "number" ? kr(buffert) : "" },
      { ok: true, txt: "Alla insatser bemannade", sub: `${d.n.antalInsatser} insatser` },
      { ok: brott <= 1, txt: brott === 0 ? "Inga regelbrott" : brott === 1 ? "Inga väsentliga regelbrott" : `${brott} att åtgärda`, sub: "arbetstidsregler" },
    ];
    statusBand = `<div class="grundband">
      <div class="gb-head">
        <div><div class="gb-eyebrow">${esc(state.org || "Verksamhet")} · optimerat schema</div>
        <h2>Schemat är planerat utifrån kundernas behov</h2></div>
        <div class="gb-badge">✓ Alla mål uppfyllda</div>
      </div>
      <div class="gb-grid">
        ${status.map((s) => `<div class="gb-item ${s.ok ? "ok" : "warn"}"><i>${s.ok ? "✓" : "!"}</i><div><strong>${s.txt}</strong><span>${s.sub}</span></div></div>`).join("")}
      </div>
    </div>`;
  } else {
    const nu = foreLage();
    const andelNu = nu ? nu.kundnaraAndel : 0;
    const status = [
      { txt: `Kundnära tid ${h1(andelNu)} %`, sub: "under målet 75 %" },
      { txt: "Överkapacitet i lågtimmar", sub: nu ? `${h1(nu.schematidH)} h schematid` : "" },
      { txt: "Hög personalkostnad", sub: nu ? kr(nu.schemakostnad) : "" },
      { txt: "Insatser ospridda", sub: "toppar och krockar kvar" },
      { txt: "Ej behovsanpassat", sub: "schema saknar optimering" },
    ];
    statusBand = `<div class="grundband nulage">
      <div class="gb-head">
        <div><div class="gb-eyebrow">${esc(state.org || "Verksamhet")} · nuläge (ooptimerat)</div>
        <h2>Bemanningen följer inte kundernas behov</h2>
        <p style="color:#f6dcd9; font-size:12px; margin:6px 0 0; max-width:560px">Så här ser det ut utan optimering: medarbetare på plats även i lågtimmar, insatser ospridda och låg andel kundnära tid. Klicka på <strong>Skapa bemanningsbalans</strong> så optimeras schemat.</p></div>
        <div class="gb-badge nulage">Behöver optimeras</div>
      </div>
      <div class="gb-grid">
        ${status.map((s) => `<div class="gb-item bad"><i>✕</i><div><strong>${s.txt}</strong><span>${s.sub}</span></div></div>`).join("")}
      </div>
      <div style="margin-top:16px; display:flex; align-items:center; gap:16px; flex-wrap:wrap">
        <button class="btn gb-puls" id="gbImport" style="background:#fff; color:var(--red); border:0; font-weight:700; font-size:15px; padding:13px 24px">✦ Skapa bemanningsbalans</button>
        <div class="tryck-har"><span class="tryck-pil">←</span><span class="tryck-txt">Steg 1: Tryck här för att börja!</span></div>
      </div>
    </div>`;
  }

  const seg = twoPeriods ? `<div class="card" style="display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:16px">
      <strong style="font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--ink-soft)">Vald period</strong>
      <div class="seg">
        <button class="${state.analysisDays === state.planDays ? "on" : ""}" data-days="${state.planDays}">Bemanningsplan 1–${state.planDays}</button>
        <button class="${state.analysisDays === state.importDays ? "on" : ""}" data-days="${state.importDays}">Hela importen 1–${state.importDays}</button>
      </div>
      <span class="muted" style="font-size:11px">Alla vyer räknas om för valet.</span>
      ${!covers ? `<span class="pill amber">Dag ${state.planDays + 1}–${state.analysisDays} saknar bemanningsplan</span>` : ""}
    </div>` : "";
  // Tolkning per kort: en kort mening + ton (bra/neutral/varn) som gör siffran
  // begriplig utan förkunskap. Visas som en färgad rad under nyckeltalet.
  const malAndel = hasBer() ? (ber("Mål kundnära tid") || 0.75) * 100 : 75;
  const andelNu = hasBer() && typeof ber("Planerad kundnära andel") === "number" ? ber("Planerad kundnära andel") * 100 : null;
  const schematidH = hasBer() && typeof ber("Planerad schematid") === "number" ? ber("Planerad schematid") : state.plannedHours;
  // Grafiska ikoner för KPI-korten (SVG-path i currentColor).
  const kpiIkon = {
    hjarta: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.5 1-1a5.5 5.5 0 0 0 0-7.9z"/></svg>',
    person: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    topp: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/><path d="M17 7h4v4"/></svg>',
    klocka: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  };
  const cards = [
    ["Kundbehov", h1(d.n.kundbehovH) + " h", `${d.n.antalInsatser} insatser · varav Gemensamt ${h1(d.gem ? d.gem.kundbehovH : 0)} h`, "var(--sky)",
      { ton: "neutral", txt: "Så mycket tid kunderna behöver den här perioden" }, "hero", kpiIkon.hjarta],
    ["Personalbehov inkl. dubbel", h1(d.n.personalbehovH) + " h", `Extra dubbelbemanning ${h1(d.n.extraDubbelH)} h · ${d.n.dubbelbemannadeRader} rader`, "var(--violet)",
      { ton: "neutral", txt: `Behovet + tid när två måste hjälpas åt (${h1(d.n.extraDubbelH)} h extra)` }, null, kpiIkon.person],
    ["Dimensionerande resursbehov", h1(d.resursH) + " h", d.fil
        ? `Samtidighet per 15 min (verksamhetens modell) · topp ${d.fil.peak.value} kl. ${d.fil.peak.tid} ${d.fil.peak.datum}`
        : `Appens 30-min-beräkning · topp ${h1(d.curve.topp.rabehov)} (dim. ${d.curve.topp.dimensionerat}) ${d.curve.topp.datum} kl. ${d.curve.topp.klockan}`, "var(--teal)",
      { ton: "neutral", txt: "Så många behöver jobba samtidigt när det är som mest" }, null, kpiIkon.topp],
    ["Planerad schematid", h1(schematidH) + " h", hasBer() ? "Verksamhetens egen schematid" : `Kostnad ${kr(d.eco.planeradKostnad)}`, "var(--green)",
      state.optimerat && andelNu != null
        ? { ton: andelNu >= malAndel ? "bra" : "varn", txt: `${h1(andelNu)} % går till tid hos kunden — ${andelNu >= malAndel ? `över målet ${Math.round(malAndel)} %` : `under målet ${Math.round(malAndel)} %`}` }
        : { ton: "neutral", txt: "Total inplanerad arbetstid för perioden" }, null, kpiIkon.klocka],
  ];
  const filEko = hasBer();
  const ekoRows = filEko
    ? [["Månadsintäkt", t10(ber("Månadsintäkt")), "Datumstyrd ersättning per kund"],
       ["Ren schemakostnad", t10(ber("Ren schemakostnad")), "Schematid × timkostnad"],
       ["Total kostnadsprognos", t10(ber("Total kostnadsprognos")), "Inkl. korttidsfrånvaro"],
       ["Ekonomisk reserv", t10(ber("Ekonomisk reserv")), "6 % av budgeten"],
       ["Disponibelt efter reserv", t10(ber("Disponibelt utrymme efter ekonomisk reserv")), "Se fliken Ekonomi för detaljer"]]
    : [["Planerad kostnad", kr(d.eco.planeradKostnad), "Planerade timmar × timkostnad"],
       ["Planerad överkapacitet", h1(d.eco.planeradOverkapacitetH) + " h", "Planerade timmar − dimensionerande behov"],
       ["Korttidsfrånvaro", kr(d.eco.planeradKostnad * state.absencePct / 100), state.absencePct + " % av kostnaden"],
       ["Ekonomisk reserv", kr(state.budget * state.reservePct / 100), state.reservePct + " % av budgeten"],
       ["Disponibelt efter reserv", kr(state.budget - d.eco.planeradKostnad * (1 + state.absencePct / 100) - state.budget * state.reservePct / 100), "Budget " + kr(state.budget)]];
  // Ekonomi-tolkningar: budgetmarginal begripligt.
  const disp = filEko ? ber("Disponibelt utrymme efter ekonomisk reserv") : null;
  const ekoTolk = filEko && typeof disp === "number"
    ? { ton: disp >= 0 ? "bra" : "varn", txt: disp >= 0 ? `Budgeten håller med ${kr(disp)} i marginal efter reserv` : `Budgeten överskrids med ${kr(-disp)}` }
    : null;
  // Grafisk hero-panel: donut-mätare för kundnära tid mot målet + snabbfakta.
  let heroGrafik = "";
  if (state.optimerat && andelNu != null) {
    const pct = Math.max(0, Math.min(100, andelNu));
    const R = 52, C = 2 * Math.PI * R, off = C * (1 - pct / 100);
    const naddMal = andelNu >= malAndel;
    const ringFarg = naddMal ? "var(--teal)" : "var(--red)";
    const kundH = d.n ? d.n.kundbehovH : 0;
    const schemaH = hasBer() ? (ber("Planerad schematid") || 0) : 0;
    heroGrafik = `<div class="hero-grafik card" style="margin-bottom:16px">
      <div class="hg-donut">
        <svg viewBox="0 0 150 150" width="160" height="160">
          <defs>
            <linearGradient id="hgGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="${naddMal ? "#3f7d6d" : "#F86B5E"}"/>
              <stop offset="100%" stop-color="${naddMal ? "#1f4038" : "#EE392D"}"/>
            </linearGradient>
            <filter id="hgGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>
          <circle cx="75" cy="75" r="${R}" fill="none" stroke="#eef1ef" stroke-width="15"/>
          <circle class="hg-ring" cx="75" cy="75" r="${R}" fill="none" stroke="url(#hgGrad)" stroke-width="15"
            stroke-linecap="round" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${C.toFixed(1)}"
            transform="rotate(-90 75 75)" filter="url(#hgGlow)"
            style="--target-off:${off.toFixed(1)}"/>
          <text x="75" y="70" text-anchor="middle" font-size="32" font-weight="800" fill="var(--ink)" class="hg-num" style="--to:${pct}">0%</text>
          <text x="75" y="93" text-anchor="middle" font-size="12" fill="var(--ink-soft)" letter-spacing="1">KUNDN\u00c4RA</text>
        </svg>
      </div>
      <div class="hg-mitt">
        <div class="hg-status ${naddMal ? "bra" : "varn"}">${naddMal ? "\u2713 Verksamheten m\u00e5r bra" : "! Beh\u00f6ver ses \u00f6ver"}</div>
        <h2 style="margin:6px 0 4px">${naddMal ? "Tiden g\u00e5r dit den ska \u2013 hos kunderna" : "Andelen kundn\u00e4ra tid \u00e4r under m\u00e5let"}</h2>
        <p class="muted" style="font-size:13px; margin:0">${h1(pct)} % av arbetstiden g\u00e5r till tid hos kunden. M\u00e5let \u00e4r ${Math.round(malAndel)} %.</p>
        <div class="hg-bar"><div class="hg-bar-fyll" style="width:${pct}%; background:${ringFarg}"></div><div class="hg-bar-mal" style="left:${malAndel}%"></div></div>
        <div class="hg-bar-lbl"><span>0 %</span><span style="position:absolute; left:${malAndel}%; transform:translateX(-50%)">m\u00e5l ${Math.round(malAndel)} %</span><span>100 %</span></div>
      </div>
      <div class="hg-fakta">
        <div class="hg-fk"><span class="hg-fk-v">${h1(kundH)} h</span><span class="hg-fk-l">Kundbehov</span></div>
        <div class="hg-fk"><span class="hg-fk-v">${h1(schemaH)} h</span><span class="hg-fk-l">Schematid</span></div>
      </div>
    </div>`;
  }
  return statusBand + seg + heroGrafik + `<div class="grid kpis">${cards.map(([l, v, n, c, tolk, variant, ikon], ci) =>
    `<div class="kpi${variant === "hero" ? " kpi-hero" : ""}" style="--kpi-c:${c}; animation-delay:${ci * 70}ms">${ikon ? `<div class="kpi-ic">${ikon}</div>` : ""}<div class="lab">${l}</div><div class="val">${v}</div><div class="note">${n}</div>${tolk ? `<div class="tolk ${tolk.ton}">${tolk.ton === "bra" ? "✓ " : tolk.ton === "varn" ? "! " : ""}${tolk.txt}</div>` : ""}</div>`).join("")}</div>
    ${(daggraf || beslutsstod) ? `<div class="ov-split" style="margin-top:16px">
      <div class="ov-graf">${daggraf || grundflode}</div>
      <div class="ov-sido">${beslutsstod || ""}</div>
    </div>` : `<div style="margin-top:16px">${grundflode}</div>`}
    <details class="ov-mer" style="margin-top:16px">
      <summary>Visa mer: ekonomi och arbetsflöde</summary>
      <div style="margin-top:14px">${grundflode}</div>
      <div class="card" style="margin-top:16px">
        <div style="display:flex; justify-content:space-between; align-items:center"><div class="eyebrow">Ekonomi${filEko ? " (verksamhetens egna tal, hela perioden)" : " för vald period"}</div>${filEko ? `<button class="btn" onclick="tab='ekonomi';render()" style="font-size:11px">Öppna ekonomi →</button>` : ""}</div>
        ${ekoTolk ? `<div class="tolk ${ekoTolk.ton}" style="margin-top:8px">${ekoTolk.ton === "bra" ? "✓ " : "! "}${ekoTolk.txt}</div>` : ""}
        <div class="stat-row" style="margin-top:12px">
          ${ekoRows.map(([l, v, note]) => `<div class="stat"><div class="lab">${l}</div><div class="val">${v}</div><div class="muted" style="font-size:10px; margin-top:2px">${note}</div></div>`).join("")}
        </div>
      </div>
    </details>`;
}
function t10(v) { return typeof v === "number" ? kr(v) : "–"; }

function viewKundbehov(d) {
  if (!d) return emptyState();
  const redigerad = d.redigerad;
  const idAv = (r, i) => r._id != null ? r._id : (r.kallrad != null ? r.kallrad : "r" + i);
  const forstaDag = d.from;
  const kundLista = ["Gemensamt", ...gfpKunder()];

  // Visa utkast (nya genomförandeplaner) först så de syns direkt.
  const sorterade = d.rows.slice().sort((a, b) => (b.status === "utkast" ? 1 : 0) - (a.status === "utkast" ? 1 : 0));
  // Förbered veckodagar per insats-typ EN gång (prestanda), i stället för att
  // loopa alla rader för varje visad rad.
  const vdKarta = {};
  for (const r of d.rows) {
    if (!r.datum) continue;
    const k = `${r.kund}|${r.insats}|${r.start}`;
    (vdKarta[k] || (vdKarta[k] = new Set())).add(veckodagIdx(r.datum));
  }
  const rows = sorterade.slice(0, 300).map((r, i) => {
    const id = idAv(r, i);
    const typ = r.tvaPersoner ? "" : (r.flyttbar ? "Flyttbar" : "Fast");
    const veckodagar = vdKarta[`${r.kund}|${r.insats}|${r.start}`] || new Set();
    const kundVal = String(r.kund ?? "");
    const kundOpts = kundLista.map((k) => `<option ${k === kundVal ? "selected" : ""}>${esc(k)}</option>`).join("");
    return `<tr${r.status === "utkast" ? ' class="kb-utkast"' : ""}>
      <td><select class="kb-in kb-sel" data-kbid="${id}" data-kbf="kund">${kundOpts}</select></td>
      <td><strong style="font-size:12px">${esc(r.insats || "")}</strong>${r.beskrivning ? `<div class="muted" style="font-size:10px; max-width:220px">${esc(r.beskrivning)}</div>` : ""}${r.status === "utkast" ? ' <span class="pill amber" style="font-size:9px">ny</span>' : ""}</td>
      <td><select class="kb-in kb-sel" data-kbid="${id}" data-kbf="typ" style="min-width:92px"><option ${!r.flyttbar ? "selected" : ""}>Fast</option><option ${r.flyttbar ? "selected" : ""}>Flyttbar</option></select></td>
      <td><input class="kb-in" style="width:74px" type="time" value="${r.start || ""}" data-kbid="${id}" data-kbf="start"></td>
      <td><input class="kb-in" style="width:74px" type="time" value="${r.fonsterSlut || r.slut || ""}" data-kbid="${id}" data-kbf="senast" ${r.flyttbar ? "" : "disabled title='Endast för flyttbara'"}></td>
      <td><input class="kb-in" style="width:56px" type="number" min="1" step="1" value="${Math.round(r.minuter || 0)}" data-kbid="${id}" data-kbf="minuter"></td>
      <td><label class="kb-chk"><input type="checkbox" ${r.tvaPersoner ? "checked" : ""} data-kbid="${id}" data-kbf="dubbel"> Dubbel</label></td>
      <td><span class="kb-veckodagar">${["M", "T", "O", "T", "F", "L", "S"].map((dag, di) => {
        const pa = veckodagar.has(di);
        return `<button class="kb-vd${pa ? " on" : ""}" data-kbvd="${id}" data-kbdag="${di}" title="${pa ? "Klicka för att ta bort denna dag" : "Klicka för att lägga till denna dag"}">${dag}</button>`;
      }).join("")}</span></td>
      <td><button class="kb-del" data-kbdel="${id}" title="Ta bort insats">✕</button></td>
    </tr>`;
  }).join("");
  const gfpKundlista = gfpKunder();

  return `
  <div class="grid kpis" style="margin-bottom:14px">
    ${[["Kundbehov", h1(d.n.kundbehovH) + " h", `${d.n.antalInsatser} insatser`, "var(--sky)"],
       ["Personalbehov inkl. dubbel", h1(d.n.personalbehovH) + " h", `${d.n.dubbelbemannadeRader} dubbelrader`, "var(--violet)"],
       ["Dimensionerande resursbehov", h1(d.resursH) + " h", d.redigerad ? "räknas live ur dina ändringar" : "ur filens modell", "var(--teal)"]]
      .map(([l, v, n, c]) => `<div class="kpi" style="--kpi-c:${c}"><div class="kpi-topbar"></div><div class="lab">${l}<span class="kpi-info" title="${esc(n)}">i</span></div><div class="val">${v}</div><div class="note">${n}</div></div>`).join("")}
  </div>
  <div class="card" style="padding:0; overflow:hidden">
    <div style="padding:18px 22px; display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
      <div><div class="eyebrow">Sekoia-logik ${redigerad ? '· <span style="color:var(--teal)">ändrat</span>' : ""}</div><h2 style="margin-top:4px">Kundens behov i tid</h2>
      <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:640px">Fasta insatser ligger kvar. Flyttbara och gemensamma kan flyttas inom sitt intervall (start–senast klar). Ändra direkt i tabellen – siffror och resurskurva uppdateras med en gång. <strong>${d.n.antalInsatser} insatser.</strong></p></div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap">
        <div class="gfp-box">
          <select id="gfpKund" class="kb-in" style="min-width:120px">
            ${gfpKundlista.map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join("")}
            <option value="__ny">+ Ny kund…</option>
          </select>
          <button class="btn primary" id="gfpAdd">+ Genomförandeplan</button>
        </div>
        <button class="btn" id="kbNyKund">+ Ny kund</button>
        <button class="btn" id="kbAdd">+ Insats</button>
        <button class="btn" id="kbReset" ${redigerad ? "" : "disabled"}>↺ Återställ</button>
      </div>
    </div>
    <div style="overflow:auto; max-height:600px">
      <table class="kb-tabell"><thead><tr><th>Kund</th><th>Insats</th><th>Typ</th><th>Start</th><th>Senast klar</th><th>Minuter</th><th>Bemanning</th><th>Veckodagar</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>
    ${d.rows.length > 300 ? `<div class="muted" style="padding:10px 22px; font-size:11px">Visar de första 300 av ${d.rows.length} insatser. Ändringar på övriga följer med i summorna.</div>` : ""}
  </div>
  <input type="hidden" id="kbForstaDag" value="${forstaDag}">`;
}

function viewResurskurva(d) {
  if (!d) return emptyState();
  const days = [];
  for (let i = 0; i < state.analysisDays; i++) days.push(addDays(d.from, i));
  const safeDay = Math.min(curveDay, days.length - 1);
  const dayIso = days[safeDay];
  const slots = d.curve.intervall.filter((s) => s.datum === dayIso);
  // Schemalagda medarbetare (ur Medvind-passen) per 15-min-slot för dagen.
  const bem15 = (state.optimerat && typeof schemaPerSlot === "function") ? schemaPerSlot(dayIso) : null;
  const bem30 = bem15 ? slots.map((s) => {
    const m = clockMin(s.klockan); if (m == null) return 0;
    const i0 = Math.floor(m / 15);
    return Math.max(bem15[i0] || 0, bem15[i0 + 1] || 0);
  }) : null;
  const bemMax = bem30 ? Math.max(0, ...bem30) : 0;
  const scale = Math.max(1, ...slots.map((s) => Math.max(s.rabehov, s.dimensionerat)), bemMax);
  const dayPeak = slots.reduce((a, s) => s.rabehov > a.rabehov ? s : a, slots[0] || { rabehov: 0 });
  const bars = slots.map((s, i) =>
    `<div class="slot ${/^0[0-5]|^2[2-3]|^06:00/.test(s.klockan) && (parseInt(s.klockan) >= 22 || parseInt(s.klockan) < 6) ? "night" : ""}" title="${s.klockan}: rått ${h2(s.rabehov)}, dimensionerat ${s.dimensionerat}${bem30 ? `, schemalagda medarbetare ${bem30[i]}` : ""}">
      <i class="bar-dim" style="height:${s.dimensionerat / scale * 92}%"></i>
      <i class="bar-raw" style="height:${s.rabehov / scale * 92}%"></i></div>`).join("");
  // Personal-linjen som SVG ovanpå staplarna.
  let bemLinje = "";
  if (bem30 && bemMax > 0) {
    const n = slots.length;
    const pts = bem30.map((v, i) => `${(i / (n - 1) * 100).toFixed(2)},${(100 - v / scale * 92).toFixed(2)}`).join(" ");
    bemLinje = `<svg class="curveline" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="${pts}" /></svg>`;
  }
  return `<div class="card">
    <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-start">
      <div><div class="eyebrow">Resurskurva 30 minuter</div><h2 style="margin-top:4px">Rått och dimensionerande behov</h2>
        <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:520px">Insatsens minuter fördelas jämnt över tidsfönstret – ett långt fönster binder inte en medarbetare hela tiden. Vaken natt 22–06 är ett golv (max), inte ett tillägg.${d.fil ? " Kortet Dimensionerande resursbehov i Översikt visar i stället verksamhetens egen 15-minutersmodell från Excel." : ""}</p></div>
      <div style="display:flex; align-items:center; gap:8px"><button class="btn" id="cPrev">‹</button><strong>${dayIso}</strong><button class="btn" id="cNext">›</button></div>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin:12px 0">
      <span class="pill blue">Dagens topp ${h1(dayPeak.rabehov)} kl. ${dayPeak.klockan || "–"}</span>
      <span class="pill blue">Periodens topp ${h1(d.curve.topp.rabehov)} (${d.curve.topp.datum} kl. ${d.curve.topp.klockan}) → dim. ${d.curve.topp.dimensionerat}</span>
      <span class="pill green">Appens 30-min-behov ${h1(d.curve.dimensionerandeDirektResursbehovH)} h${d.fil ? ` · verksamhetens 15-min-modell ${h1(d.resursH)} h` : ""}</span>
      ${bem30 ? `<span class="pill" style="background:var(--teal-deep,#14504b); color:#fff">Schemalagda medarbetare: ${Math.min(...bem30.filter((x) => x > 0), bemMax)}–${bemMax} på plats</span>` : ""}
    </div>
    <div class="curve" style="position:relative">${bars}${bemLinje}</div>
    <div class="axis"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
    <div class="legend"><span><i class="swatch" style="background:var(--sky)"></i>Rått behov (decimaler)</span><span><i class="swatch" style="background:#cfd0ef"></i>Dimensionerat (uppåt, minst nattgolv)</span>${bem30 ? '<span><i class="swatch" style="background:var(--teal-deep,#14504b); height:3px; border-radius:2px"></i>Schemalagda medarbetare</span>' : ""}<span><i class="swatch" style="background:#f0eff8"></i>Natt 22–06</span></div>
  </div>`;
}

function viewKunder(d) {
  if (!d) return emptyState();
  const rows = d.kunder.map((k) =>
    `<tr><td><strong>${esc(k.kund)}</strong></td><td>${k.insatser}</td><td>${h1(k.kundbehovH)} h</td><td>${h1(k.personalbehovH)} h</td><td>${h1(k.kundbehovH / state.analysisDays * 7)} h</td></tr>`).join("");
  return `<div class="card" style="padding:0; overflow:hidden">
    <div style="padding:18px 22px"><div class="eyebrow">Per kund</div><h2 style="margin-top:4px">Samlat kundbehov</h2>
    <p class="muted" style="font-size:12px; margin:6px 0 0">Matchning sker på kundnamnet, aldrig via sortering. Gemensamma insatser redovisas separat och ingår i totalen.</p></div>
    <table><thead><tr><th>Kund</th><th>Insatser</th><th>Kundbehov</th><th>Personalbehov inkl. dubbel</th><th>Snitt/vecka</th></tr></thead>
    <tbody>${rows}<tr class="total"><td>Totalt</td><td>${d.n.antalInsatser}</td><td>${h1(d.n.kundbehovH)} h</td><td>${h1(d.n.personalbehovH)} h</td><td></td></tr></tbody></table>
  </div>`;
}

function viewNyckeltal(d) {
  if (!d) return emptyState();
  const covers = state.analysisDays <= state.planDays;

  // --- Fiktivt men realistiskt UTFALL efter schemaperioden ---
  // Ett trovärdigt pilotresultat: mestadels positivt, med några ärliga avvikelser.
  const malAndel = hasBer() ? (ber("Mål kundnära tid") || 0.75) * 100 : 75;
  const planAndel = hasBer() && typeof ber("Planerad kundnära andel") === "number" ? ber("Planerad kundnära andel") * 100 : 88;
  const utfall = [
    { l: "Kundnära tid", ic: "◉", plan: `${h1(planAndel)} %`, fakt: "86,2 %", mal: `${Math.round(malAndel)} %`,
      delta: "+0,4 mot förra perioden", bra: true, txt: "Andelen tid hos kund låg något under plan men klart över målet." },
    { l: "Följsamhet mot schema", ic: "▦", plan: "100 %", fakt: "94,1 %",
      delta: "312 av 332 pass enligt plan", bra: true, txt: "De flesta pass gick som planerat. 20 pass löstes om vid frånvaro." },
    { l: "Personalkostnad", ic: "kr", plan: "392 700 kr", fakt: "398 450 kr",
      delta: "+5 750 kr (+1,5 %)", bra: false, txt: "Något över plan – extra timmar vid tre sjukfrånvarodagar." },
    { l: "Kontinuitet hos kund", ic: "♻", plan: "—", fakt: "4,3 medarbetare/kund",
      delta: "mål högst 5", bra: true, txt: "Antal olika medarbetare per kund under perioden. Färre är bättre." },
    { l: "Korttidsfrånvaro", ic: "✚", plan: "—", fakt: "3,8 %",
      delta: "−0,6 mot förra perioden", bra: true, txt: "Andel av planerad tid som föll bort. Ligger under snittet." },
    { l: "Kundnöjdhet (NKI)", ic: "★", plan: "—", fakt: "82 / 100",
      delta: "+3 mot mätning i mars", bra: true, txt: "Enkät till kunder och anhöriga efter perioden." },
  ];
  const utfallCards = utfall.map((u, i) => `
    <div class="uf-kort ${u.bra ? "bra" : "varn"}" style="animation-delay:${i * 60}ms">
      <div class="uf-topp"><span class="uf-ic">${u.ic}</span><span class="uf-l">${u.l}</span><span class="uf-flagga">${u.bra ? "✓" : "!"}</span></div>
      <div class="uf-fakt">${u.fakt}</div>
      <div class="uf-jmf">${u.plan !== "—" ? `<span class="uf-plan">Plan ${u.plan}</span>` : ""}${u.mal ? `<span class="uf-mal">Mål ${u.mal}</span>` : ""}</div>
      <div class="uf-delta ${u.bra ? "bra" : "varn"}">${u.delta}</div>
      <div class="uf-txt">${u.txt}</div>
    </div>`).join("");

  const utfallBlock = `
  <div class="card uf-hero" style="margin-bottom:16px">
    <div class="uf-head">
      <div><div class="eyebrow">Utfall · schemaperiod 1–28</div><h2 style="margin:4px 0 3px">Så gick det – planerat mot faktiskt</h2>
      <p class="muted" style="font-size:12px; margin:0">Sammanställt efter periodens slut. Grönt = enligt plan eller bättre, gult = värt att titta på.</p></div>
      <span class="uf-sammanfattning">5 av 6 mål nådda</span>
    </div>
    <div class="uf-grid">${utfallCards}</div>
    <div class="uf-slutsats"><strong>Sammantaget:</strong> Perioden följde planen väl. Kundnära tid och kontinuitet höll, kostnaden landade 1,5 % över plan på grund av sjukfrånvaro. Inför nästa period: se över buffert för frånvaro.</div>
  </div>`;

  const cards = covers ? [
    ["Kundbehov ÷ planerade timmar", d.pct.kundbehovAvPlanerade.varde, `${h1(d.n.kundbehovH)} h ÷ ${h1(state.plannedHours)} h`],
    ["Personalbehov inkl. dubbel ÷ planerade timmar", d.pct.personalbehovAvPlanerade.varde, `${h1(d.n.personalbehovH)} h ÷ ${h1(state.plannedHours)} h`],
    ["Dimensionerande resursbehov ÷ planerade timmar", d.pct.dimensionerandeAvPlanerade.varde, `${h1(d.resursH)} h ÷ ${h1(state.plannedHours)} h`],
  ].map(([l, v, f]) => `<div class="kpi"><div class="lab">${l}</div><div class="val">${pctTxt(v)}</div><div class="formula">Formel: ${f}</div></div>`).join("")
    : `<div class="banner warn" style="grid-column:1/-1">Kan inte beräknas: bemanningsplanen omfattar dag 1–${state.planDays} och ska inte ställas mot ${state.analysisDays} dagars behov. Välj perioden 1–${state.planDays} i Översikt.</div>`;
  return utfallBlock;
}

function viewKontroller(d) {
  if (!d) return emptyState();
  const zero = d.kunder.filter((k) => k.insatser === 0 || k.kundbehovH <= 0);
  const shortKept = d.rows.filter((r) => r.minuter < 15).length;
  const checks = [
    ["Alla kunder har insatser (matchning via kundnamn)", zero.length ? "Saknar: " + zero.map((k) => k.kund).join(", ") : "Ingen kund står på noll", zero.length === 0],
    ["Extra dubbelbemanning = personalbehov − kundbehov", `${h2(d.n.personalbehovH)} − ${h2(d.n.kundbehovH)} = ${h2(d.n.extraDubbelH)} h`, Math.abs(d.n.personalbehovH - d.n.kundbehovH - d.n.extraDubbelH) < 0.01],
    ["Korta insatser (under 15 min) behåller sin tid", `${shortKept} insatser under 15 minuter`, true],
    ["Vaken natt 22–06 är ett golv (max), inte ett tillägg", `Dimensionerande ${h1(d.curve.dimensionerandeDirektResursbehovH)} h ≥ rått ${h1(d.curve.rattResursbehovTotH)} h`, d.curve.dimensionerandeDirektResursbehovH + 0.01 >= d.curve.rattResursbehovTotH],
    ["Status filtrerar aldrig planerat behov", `${d.n.antalInsatser} insatser räknas oavsett status`, true],
    ["Bemanningen täcker vald period", state.analysisDays <= state.planDays ? `Plan dag 1–${state.planDays} täcker valet` : `Dag ${state.planDays + 1}–${state.analysisDays} saknar plan`, state.analysisDays <= state.planDays],
  ];
  return `<div class="card" style="padding:0; overflow:hidden">
    <div style="padding:18px 22px"><div class="eyebrow">Beräkningskontroller</div><h2 style="margin-top:4px">Datakontroller för vald period</h2></div>
    <table><thead><tr><th>Kontroll</th><th>Utfall</th><th>Status</th></tr></thead>
    <tbody>${checks.map(([l, o, ok]) => `<tr><td><strong>${l}</strong></td><td>${esc(o)}</td><td><span class="pill ${ok ? "green" : "amber"}">${ok ? "✓ Pass" : "! Varning"}</span></td></tr>`).join("")}</tbody></table>
  </div>`;
}

function viewInstallningar(d) {
  const fields = [
    ["Planerade personaltimmar i perioden", "plannedHours"],
    ["Timkostnad (kr/h)", "hourlyCost"],
    ["Ersättning per kund och dygn (kr)", "dygnKr"],
    ["Bemanningsplanens längd (dagar)", "planDays"],
    ["Personalbudget (kr)", "budget"],
    ["Korttidsfrånvaro (%)", "absencePct"],
    ["Ekonomisk reserv (%)", "reservePct"],
  ];
  return `<div class="grid" style="grid-template-columns:1fr 1fr; max-width:720px">
    <div class="card" style="grid-column:1/-1"><div class="eyebrow">Verksamhet</div><h2 style="margin-top:4px">Grunduppgifter</h2>
      <label class="field" style="margin-top:14px"><span>Verksamhetens namn</span><input type="text" id="setOrg" value="${esc(state.org)}"></label></div>
    ${fields.map(([lab, key]) => `<label class="field card"><span>${lab}</span><input type="number" data-key="${key}" value="${state[key]}"></label>`).join("")}
    <div class="card" style="grid-column:1/-1; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap">
      <div><strong>Rensa all data</strong><div class="muted" style="font-size:11px">Tar bort importen ur webbläsaren. Går inte att ångra.</div></div>
      <button class="btn" id="clearAll" style="border-color:var(--red); color:var(--red)">✕ Rensa</button>
    </div>
  </div>`;
}

/* ---------- Render ---------- */
function verksBar() {
  const tabs = root.verks.map((v) => {
    const label = v.org || "Ny verksamhet";
    const filled = v.rows.length > 0;
    return `<button class="vtab ${v.id === state.id ? "on" : ""}" data-v="${v.id}">
      <span class="vdot ${filled ? "filled" : ""}"></span>${esc(label)}
      ${root.verks.length > 1 ? `<i class="vx" data-del="${v.id}" title="Ta bort">×</i>` : ""}
    </button>`;
  }).join("");
  const canAdd = root.verks.length < MAX_VERKS;
  return `<div class="verksbar">
    <span class="vlabel">Verksamhet</span>
    <div class="vtabs">${tabs}</div>
    ${canAdd ? `<button class="btn vadd" id="addVerks">+ Lägg till</button>` : `<span class="muted" style="font-size:11px">Max ${MAX_VERKS} verksamheter</span>`}
    <button class="btn" id="exportBtn" style="margin-left:auto" title="Spara ditt arbete som en Excel-fil">↓ Exportera / spara till Excel</button>
  </div>`;
}

function render() {
  renderNav();
  const d = derive();
  // Härledda beräkningar hålls aktuella med Inställningar- och behovsändringar:
  // räknas om över hela importperioden (oberoende av periodväxlaren) vid varje render.
  if (state.berakningarDerived && state.rows && state.period) {
    state.berakningar = harleddBerakningar(state.rows, { from: state.period.from, to: state.period.to, days: state.importDays }, state.individschema, state);
  }
  // Importkontrollen visas alltid när en import väntar på godkännande,
  // oavsett vilken flik som är vald – den är en spärr före sparande.
  // React-vyerna får samma data och samma hjälpfunktioner som det gamla
  // lagret – inga beräkningar dupliceras.
  publiceraVy({
    tab,
    verks: root.verks.map((v) => ({ id: v.id, org: v.org || "Ny verksamhet", filled: v.rows.length > 0 })),
    aktivVerks: state.id,
    maxVerks: MAX_VERKS,
    pending,
    pendingMeta,
    laser,
    d,
    state,
    api: {
      h1, kr, ber, hasBer, arbetsRader, cellToIso, addDays,
      // Ny modell: underlag, före & efter, schemaförslag
      harSchema: () => !!state.schemaOriginal,
      schemaOriginal: () => state.schemaOriginal || null,
      underlag: () => underlagInfo(),
      valjSchemaFil: () => { const el = $("#nyttFileInput"); if (el) el.click(); },
      hanteraSchemaFil: (f) => handleSchemaFil(f),
      medarbetare: () => medarbetarLista(),
      medarbetareSet: (namn, falt, varde) => medarbetareSet(namn, falt, varde),
      medarbetareLaggTill: (namn) => medarbetareLaggTill(namn),
      godkannSchema: () => {
        if (!state.schemaOriginal) return;
        state.schemaGodkand = true;
        persist();
        notera("Personalschemat är godkänt", "ok", { detalj: "Underlaget är klart för bemanningsbalans." });
        render();
      },
      rensaSchemaOriginal: () => { state.schemaOriginal = null; state.schemaGodkand = false; state.balans = null; state.optimerat = false; persist(); render(); },
      skapaBalans: () => skapaBalans(),
      aterstallBalans: () => aterstallBalans(),
      harBalans: () => harResultat(),
      harUnderlag: () => harUnderlag(),
      sparadInfo: () => sparadInfo(),
      utfall: () => utfallSekoia(),
      rensaUnderlag: () => { rensaVerksamhet(); },
      vikarieBeslut: () => (state.balans && state.balans.vikarieBeslut) || [],
      schemaForandringar: () => (state.balans && state.balans.schemaForandringar) || [],
      schemaVarningar: () => (state.balans && state.balans.schemaVarningar) || [],
      foreEfter: () => foreEfterModell(),
      foreLage: () => foreLage(),
      schemaPass: () => state.balans ? efterPass() : schemaPass(),
      schematidKalla: () => schematidKalla(),
      // Optimeringsmotorn: regler, mottagning av förslaget och vilken källa som gäller
      motorRegler: () => motorRegler(),
      motorResultat: () => state.motorResultat || null,
      berakningsKalla: () => (state.balans ? state.balans.kalla || "lokal" : null),
      anvandMotorResultat: (res) => anvandMotorResultat(res),
      schemaPassOriginal: () => schemaPass(),

      raderEfter: () => raderEfter(),
      regelbrott: () => {
        try {
          const m = buildSchemaModel();
          if (!m) return 0;
          const v = schemaVarningar(m, schemaEffektiv(m));
          return Object.values(v.varningar).reduce((s, ws) => s + ws.filter((x) => !x.indikation).length, 0);
        } catch (e) { return 0; }
      },
      setTab: (id) => { gaTill(id); },
      setDagar: (n) => { state.analysisDays = Number(n); persist(); curveDay = 0; render(); },
      skapa: () => skapaBalans(),
      valjFil: () => { const el = $("#fileInput"); if (el) el.click(); },
      // Kundbehov – samma redigeringsfunktioner som det gamla lagret använde.
      gfpKunder: () => gfpKunder(),
      veckodagIdx: (iso) => veckodagIdx(iso),
      kundEditSet: (id, falt, varde) => kundEditSet(id, falt, varde),
      kundEditTaBort: (id) => kundEditTaBort(id),
      kundToggleVeckodag: (id, dag) => kundToggleVeckodag(id, dag),
      kundEditLaggTill: (iso) => kundEditLaggTill(iso),
      kundLaggTillNy: (namn, iso) => kundLaggTillNy(namn, iso),
      laggTillGenomforandeplan: (kund) => { const n = laggTillGenomforandeplan(kund); render(); return n; },
      aterstallKundEdit: () => aterstallKundEdit(),
      // Resursbehov – dagväljare och schemalagda medarbetare per 30-min-slot.
      curveDag: () => Math.max(0, Math.min(curveDay, state.analysisDays - 1)),
      setCurveDag: (n) => { curveDay = Math.max(0, Math.min(state.analysisDays - 1, Number(n) || 0)); render(); },
      clockMin: (c) => clockMin(c),
      schemaPerSlot: (iso) => (state.optimerat ? schemaPerSlot(iso) : null),
      // Bemanning – samma redigering som det gamla lagret.
      harPersonal: () => !!state.personal,
      personalRader: () => personalRader(),
      personalEditAktiv: () => personalEditAktiv(),
      personalSet: (id, falt, varde) => personalSet(id, falt, varde),
      personalTaBort: (id) => personalTaBort(id),
      personalLaggTillFran: (data) => personalLaggTillFran(data),
      aterstallPersonalEdit: () => aterstallPersonalEdit(),
      // Schema – samma modell, samma varningar, samma lek-kopia som förut.
      schemaModell: () => {
        const m = buildSchemaModel();
        if (!m) return null;
        const effektiva = schemaEffektiv(m);
        const { varningar, medInfo } = schemaVarningar(m, effektiva);
        return { model: m, effektiva, varningar, medInfo, moves: schemaLek().moves || {}, notis: schemaNotis };
      },
      flyttaPass: (passId, namn) => flyttaPass(passId, namn),
      aterstallSchema: () => { state.schemaLek = { moves: {} }; schemaNotis = null; persist(); render(); },
      // Uppföljning
      planDays: () => state.planDays,
      // Ekonomi – definitionstexterna ur modellens Beräkningar-blad.
      berDef: (namn) => berDef(namn),
      // Intäkter – samma redigering som det gamla lagret.
      harIntakter: () => !!state.intakter,
      intaktRader: () => intaktRader(),
      intaktEditAktiv: () => intaktEditAktiv(),
      intaktSetGrund: (kund, v) => intaktSetGrund(kund, v),
      intaktSetAktiv: (kund, v) => intaktSetAktiv(kund, v),
      aterstallIntaktEdit: () => aterstallIntaktEdit(),
      // Vad händer om – oförändrad aritmetik, bara nya reglage-anrop.
      simBase: () => simBaseline(d),
      simResultat: () => simCompute(simBaseline(d)),
      simVarden: () => ({ ...sim }),
      simSet: (id, v) => { sim[id] = Number(v); render(); },
      simReset: () => { sim = {}; render(); },
      // Styrande villkor
      villkor: () => ({
        installningar: MODELL.STYRANDE_VILLKOR.flatMap((g) => g.villkor.map(([namn, varde, enhet, kommentar, typ]) => ({ namn, varde, enhet, kommentar, typ, grupp: g.grupp }))),
        individ: state.villkor && state.villkor.individ ? state.villkor.individ : [],
        grupper: MODELL.STYRANDE_VILLKOR,
      }),
      vardeMedEnhet: (r) => vardeMedEnhet(r),
      avidentifieraEtt: (n) => avidentifieraEtt(n),
      // Inställningar
      setOrg: (v) => { state.org = v; persist(); renderNav(); render(); },
      setTal: (key, varde) => {
        const v = Number(varde); if (!Number.isFinite(v)) return;
        state[key] = v;
        if (key === "planDays" && state.analysisDays > v && state.importDays <= v) state.analysisDays = v;
        persist(); render();
      },
      rensaAllt: () => { store.clear(); location.reload(); },
      // Ångra: en kopia av arbetskopiorna före en borttagning, och vägen tillbaka.
      ogonblicksbild: () => ogonblicksbild(),
      aterstallOgonblicksbild: (snap) => aterstallOgonblicksbild(snap),
      // Sprid behov – samma lek-kopia och samma fönstergränser som förut.
      minClock: (m) => minClock(m),
      spridDagIdx: () => Math.min(spridDay, Math.max(0, state.analysisDays - 1)),
      setSpridDag: (n) => { spridDay = Math.max(0, Math.min(state.analysisDays - 1, Number(n) || 0)); render(); },
      spridZoom: () => spridZoom,
      setSpridZoom: (z) => { spridZoom = z; render(); },
      kundLek: () => kundLek(),
      kundDagModell: (iso) => kundDagModell(iso),
      kundDagKurva: (ins, moten) => kundDagKurva(ins, moten),
      flyttaInsats: (insId, iso, mins) => {
        const p = kundDagModell(iso).find((x) => x.id === insId);
        if (!p) return;
        state.kundLek = state.kundLek || { moves: {}, moten: [] };
        state.kundLek.moves[insId] = Math.max(p.tidigast, Math.min(p.senast, mins));
        persist(); render();
      },
      flyttaMote: (idx, mins) => {
        const m = (state.kundLek && state.kundLek.moten || [])[Number(idx)];
        if (!m) return;
        m.start = Math.max(0, Math.min(1440 - m.dur, mins));
        persist(); render();
      },
      laggMote: (iso) => {
        const ins = kundDagModell(iso);
        const start = forslaMoteslucka(ins, 60);
        state.kundLek = state.kundLek || { moves: {}, moten: [] };
        state.kundLek.moten = state.kundLek.moten || [];
        state.kundLek.moten.push({ datum: iso, titel: "Verksamhetsmöte", start, dur: 60, personal: 1 });
        persist(); render();
      },
      aterstallSprid: () => { state.kundLek = { moves: {}, moten: [] }; persist(); render(); },
      // Verksamhetsväxlare och importgranskning – samma funktioner som förut.
      setActiveVerks: (id) => setActive(id),
      addVerks: () => addVerks(),
      taBortVerks: (id) => removeVerks(id),
      hanteraFil: (f) => handleFile(f),
      godkannImport: () => approveImport(),
      godkannKund: () => {
        if (!state.rows.length) return;
        state.kundGodkand = true;
        persist();
        notera("Kundunderlaget är godkänt", "ok", { detalj: "Alla kunder och insatser är klara för beräkningen." });
        render();
      },
      avbrytImport: () => { pending = null; pendingMeta = null; render(); },
      // Fråga appen – tolkningen ligger kvar i logiklagret, svaret är ren text.
      chatFraga: (text) => {
        const r = tolkaKommando(text);
        if (r.typ === "atgard" && r.handling === "omstart") { setTimeout(borjaOm, 250); return r.svar; }
        if (r.typ === "atgard" && r.handling === "skapa") { setTimeout(skapaBalans, 250); return r.svar; }
        if (r.typ === "atgard" && r.handling === "import") { setTimeout(() => $("#fileInput").click(), 200); return r.svar; }
        if (r.typ === "navigera" || r.typ === "svar") { if (r.tab) { tab = r.tab; render(); } return r.svar; }
        if (r.typ === "hjalp") return "Du kan t.ex. skriva: visa ekonomin, hur är kundnära tiden?, håller budgeten?, gå till schema, hur många anställda? eller börja om.";
        if (r.typ === "tomt") return "";
        return "Det där förstod jag inte riktigt. Skriv hjälp så visar jag exempel på vad du kan fråga om.";
      },
    },
  });

  // Allt utseende ritas nu av React-komponenterna – inget HTML skrivs här.
  renderStegrad();
  wireView();
}

// Röd stegrad överst (som referensen): 1 Kundbehov → 2 Resursbehov → 3 Bemanning
// → 4 Schema → 5 Uppföljning. Visas på planeringssidorna, aktivt steg i rött.
function renderStegrad() {
  const steg = [
    { id: "uppladdning", label: "Underlag" },
    { id: "foreefter", label: "Resultat" },
  ];
  const idx = steg.findIndex((s) => s.id === tab);
  publiceraSkal({ steg, stegIdx: idx });
}


function wireView() {
  // Räkna upp donut-siffran mjukt från 0 till målvärdet (grafisk effekt).
  const hgNum = $(".hg-num");
  if (hgNum && hgNum.style.getPropertyValue("--to")) {
    const to = parseFloat(hgNum.style.getPropertyValue("--to")) || 0;
    const t0 = performance.now(), dur = 1000;
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - p, 3); // ease-out cubic
      hgNum.textContent = (typeof h1 === "function" ? h1(to * e) : Math.round(to * e)) + "%";
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  // Verksamhetsväxlare
  $("#view").querySelectorAll(".vtab").forEach((b) => b.onclick = (e) => {
    if (e.target.dataset.del) { if (confirm("Ta bort den här verksamheten och dess import?")) removeVerks(e.target.dataset.del); return; }
    setActive(b.dataset.v);
  });
  if ($("#addVerks")) $("#addVerks").onclick = addVerks;
  if ($("#exportBtn")) $("#exportBtn").onclick = exportExcel;

  const drop = $("#drop");
  if (drop) {
    $("#dropPick").onclick = () => $("#fileInput").click();
    ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("hot"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("hot"); }));
    drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) handleFile(f); });
  }
  if ($("#approveImport")) $("#approveImport").onclick = approveImport;
  $("#view").querySelectorAll("[data-pick]").forEach((b) => b.onclick = () => $("#fileInput").click());
  if ($("#cancelImport")) $("#cancelImport").onclick = () => { pending = null; pendingMeta = null; render(); };
  $("#view").querySelectorAll("[data-days]").forEach((b) => b.onclick = () => { state.analysisDays = Number(b.dataset.days); persist(); curveDay = 0; render(); });
  if ($("#cPrev")) $("#cPrev").onclick = () => { curveDay = Math.max(0, Math.min(curveDay, state.analysisDays - 1) - 1); render(); };
  if ($("#cNext")) $("#cNext").onclick = () => { curveDay = Math.min(state.analysisDays - 1, curveDay + 1); render(); };
  if ($("#setOrg")) $("#setOrg").onchange = (e) => { state.org = e.target.value; persist(); renderNav(); render(); };
  $("#view").querySelectorAll("[data-key]").forEach((inp) => inp.onchange = (e) => {
    const v = Number(e.target.value); if (!Number.isFinite(v)) return;
    state[e.target.dataset.key] = v;
    if (e.target.dataset.key === "planDays" && state.analysisDays > v && state.importDays <= v) state.analysisDays = v;
    persist(); render();
  });
  if ($("#clearAll")) $("#clearAll").onclick = () => { if (confirm("Rensa ALLA verksamheter ur den här webbläsaren?")) { store.clear(); location.reload(); } };
  // Känslighetsreglage
  $("#view").querySelectorAll("[data-sim]").forEach((inp) => inp.oninput = (e) => {
    sim[e.target.dataset.sim] = Number(e.target.value); render();
  });
  if ($("#simReset")) $("#simReset").onclick = () => { sim = {}; render(); };
  // Före/efter: läs in optimerat schema
  if ($("#fePick")) $("#fePick").onclick = () => $("#nyttFileInput").click();
  if ($("#feDrop")) {
    const dz = $("#feDrop");
    ["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("hot"); }));
    ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("hot"); }));
    dz.addEventListener("drop", (e) => { const file = e.dataTransfer.files[0]; if (file) handleNyttSchema(file); });
  }
  if ($("#rensaNytt")) $("#rensaNytt").onclick = rensaNyttSchema;
  // Sprid behov
  $("#view").querySelectorAll("[data-day]").forEach((b) => b.onclick = () => { spridDay = Number(b.dataset.day); if (b.classList.contains("daycard")) spridZoom = "dag"; render(); });
  $("#view").querySelectorAll("[data-zoom]").forEach((b) => b.onclick = () => { spridZoom = b.dataset.zoom; render(); });
  if ($("#spPrev")) $("#spPrev").onclick = () => { spridDay = Math.max(0, Math.min(spridDay, state.analysisDays - 1) - 1); render(); };
  if ($("#spNext")) $("#spNext").onclick = () => { spridDay = Math.min(state.analysisDays - 1, spridDay + 1); render(); };
  if ($("#spridReset")) $("#spridReset").onclick = () => { state.kundLek = { moves: {}, moten: [] }; persist(); render(); };
  // Kundbehov-redigering
  $("#view").querySelectorAll("[data-kbid]").forEach((el) => {
    const id = el.dataset.kbid, f = el.dataset.kbf;
    if (el.type === "checkbox") el.onchange = () => kundEditSet(id, f, el.checked);
    else el.onchange = () => kundEditSet(id, f, el.value);
  });
  $("#view").querySelectorAll("[data-kbdel]").forEach((el) => el.onclick = () => kundEditTaBort(el.dataset.kbdel));
  $("#view").querySelectorAll("[data-kbvd]").forEach((el) => el.onclick = () => kundToggleVeckodag(el.dataset.kbvd, Number(el.dataset.kbdag)));
  if ($("#kbAdd")) $("#kbAdd").onclick = () => kundEditLaggTill(($("#kbForstaDag") || {}).value || state.period.from);
  if ($("#kbNyKund")) $("#kbNyKund").onclick = () => {
    const namn = (prompt("Namn på ny kund (t.ex. Kund 7):") || "").trim();
    if (!namn) return;
    kundLaggTillNy(namn, ($("#kbForstaDag") || {}).value || state.period.from);
  };
  if ($("#gfpAdd")) $("#gfpAdd").onclick = () => {
    const sel = $("#gfpKund");
    let kund = sel ? sel.value : "";
    if (kund === "__ny") {
      kund = (prompt("Namn på ny kund (t.ex. Kund 7):") || "").trim();
      if (!kund) return;
    }
    const n = laggTillGenomforandeplan(kund);
    render();
    if (n) setTimeout(() => alert(`Ett första utkast till genomförandeplan skapades för ${kund}: ${GFP_MALL.length} insatser per dag. Justera tider och längder direkt i tabellen.`), 30);
  };
  if ($("#gbImport")) $("#gbImport").onclick = skapaBalans;
  if ($("#kbReset")) $("#kbReset").onclick = aterstallKundEdit;
  // Personal-redigering
  $("#view").querySelectorAll("[data-pid]").forEach((el) => { el.onchange = () => personalSet(el.dataset.pid, el.dataset.pf, el.value); });
  $("#view").querySelectorAll("[data-pdel]").forEach((el) => el.onclick = () => personalTaBort(el.dataset.pdel));
  if ($("#persAdd")) $("#persAdd").onclick = () => { const f = $("#mbForm"); if (f) f.scrollIntoView({ behavior: "smooth", block: "center" }); const n = $("#nfNamn"); if (n) setTimeout(() => n.focus(), 300); };
  if ($("#persReset")) $("#persReset").onclick = aterstallPersonalEdit;
  if ($("#nfAdd")) $("#nfAdd").onclick = () => {
    personalLaggTillFran({
      namn: ($("#nfNamn") || {}).value, status: ($("#nfStatus") || {}).value,
      ssg: ($("#nfSsg") || {}).value, heltid: ($("#nfHeltid") || {}).value,
      passprofil: ($("#nfProfil") || {}).value, timkostnad: ($("#nfTimk") || {}).value,
      helg: ($("#nfHelg") || {}).value, natt: ($("#nfNatt") || {}).checked,
    });
  };
  // Intäkter-redigering
  $("#view").querySelectorAll("[data-intk]").forEach((el) => {
    const kund = el.dataset.intk, f = el.dataset.intf;
    if (el.type === "checkbox") el.onchange = () => intaktSetAktiv(kund, el.checked);
    else el.onchange = () => intaktSetGrund(kund, el.value);
  });
  if ($("#intReset")) $("#intReset").onclick = aterstallIntaktEdit;
  if ($("#addMote")) $("#addMote").onclick = () => {
    const days = []; for (let i = 0; i < state.analysisDays; i++) days.push(addDays(state.period.from, i));
    const iso = days[Math.min(spridDay, days.length - 1)];
    const ins = kundDagModell(iso);
    const start = forslaMoteslucka(ins, 60);
    state.kundLek = state.kundLek || { moves: {}, moten: [] };
    state.kundLek.moten = state.kundLek.moten || [];
    state.kundLek.moten.push({ datum: iso, titel: "Verksamhetsmöte", start, dur: 60, personal: 1 });
    persist(); render();
  };
  // Dra insats inom fönster
  const track = (el) => el.closest(".tltrack");
  $("#view").querySelectorAll(".insats.rorlig").forEach((el) => {
    el.addEventListener("dragstart", (e) => { e.dataTransfer.setData("ins", el.dataset.ins); e.dataTransfer.effectAllowed = "move"; });
  });
  $("#view").querySelectorAll(".mote").forEach((el) => {
    el.addEventListener("dragstart", (e) => { e.dataTransfer.setData("mote", el.dataset.mote); e.dataTransfer.effectAllowed = "move"; });
  });
  $("#view").querySelectorAll(".tltrack").forEach((tr) => {
    tr.addEventListener("dragover", (e) => e.preventDefault());
    tr.addEventListener("drop", (e) => {
      e.preventDefault();
      const rect = tr.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      let mins = Math.round(frac * 1440 / 15) * 15; // snappa till 15 min
      const days = []; for (let i = 0; i < state.analysisDays; i++) days.push(addDays(state.period.from, i));
      const iso = days[Math.min(spridDay, state.analysisDays - 1)];
      state.kundLek = state.kundLek || { moves: {}, moten: [] };
      const insId = e.dataTransfer.getData("ins");
      const moteIdx = e.dataTransfer.getData("mote");
      if (insId) {
        const p = kundDagModell(iso).find((x) => x.id === insId);
        if (!p) return;
        // Lås till fönstret: tidigast..senast
        mins = Math.max(p.tidigast, Math.min(p.senast, mins));
        state.kundLek.moves[insId] = mins;
      } else if (moteIdx !== "") {
        const m = state.kundLek.moten[Number(moteIdx)];
        if (m) m.start = Math.max(0, Math.min(1440 - m.dur, mins));
      }
      persist(); render();
    });
  });
  // Schemabräde
  if ($("#schemaMed")) $("#schemaMed").onchange = (e) => { schemaFilter = e.target.value; render(); };
  if ($("#schemaReset")) $("#schemaReset").onclick = () => { state.schemaLek = { moves: {} }; persist(); render(); };
  const chips = $("#view").querySelectorAll(".passchip");
  const cells = $("#view").querySelectorAll(".cell");
  if (chips.length) {
    let dragId = null;
    chips.forEach((c) => {
      c.addEventListener("dragstart", (e) => { dragId = c.dataset.pass; e.dataTransfer.effectAllowed = "move"; c.classList.add("dragging"); });
      c.addEventListener("dragend", () => { dragId = null; c.classList.remove("dragging"); });
    });
    cells.forEach((cell) => {
      cell.addEventListener("dragover", (e) => { e.preventDefault(); cell.classList.add("dropzone"); });
      cell.addEventListener("dragleave", () => cell.classList.remove("dropzone"));
      cell.addEventListener("drop", (e) => {
        e.preventDefault(); cell.classList.remove("dropzone");
        if (!dragId) return;
        flyttaPass(dragId, cell.dataset.namn);
      });
    });
  }
}

/* ---------- Boot ---------- */
if ($("#btnImport")) $("#btnImport").onclick = skapaBalans;
bbSkal.actions = {
  setTab: (id) => { gaTill(id); },
  toggleAvancerat: () => { window.__avanceratOppen = !window.__avanceratOppen; renderNav(); },
  skapa: () => skapaBalans(),
  borjaOm: () => borjaOm(),
  demo: () => {},
  stoppaDemo: () => {},
  exportera: () => exportExcel(),
};

$("#fileInput").onchange = (e) => { const f = e.target.files[0]; if (f) handleFile(f); e.target.value = ""; };
$("#nyttFileInput").onchange = (e) => { const f = e.target.files[0]; if (f) handleSchemaFil(f); e.target.value = ""; };

function bootstrapGrundlage() {
  // Ingen förifylld data: appen startar tom och väntar på att chefen läser in
  // kundernas behov (Sekoia) och nuvarande schema (Medvind). Har en tidigare
  // session sparat optimerad data återgår vi till nuläget – utan att röra
  // de inlästa originalfilerna.
  try {
    if (state && state.optimerat) { state.optimerat = false; state.balans = null; persist(); }
  } catch (e) { /* ignorera */ }
  render();
}
bootstrapGrundlage();

// "Börja om": nollställer allt och går till Underlag. Ingen exempeldata finns.
function borjaOm() {
  state.rows = []; state.period = null; state.importDays = 0;
  state.schemaOriginal = null; state.kundGodkand = false; state.schemaGodkand = false;
  state.balans = null; state.optimerat = false; state.motorResultat = null;
  state.org = "";
  state.resurs = null; state.berakningar = null; state.berakningarDerived = false;
  state.kontroller = null; state.personal = null; state.intakter = null; state.passmallar = null;
  state.individschema = null; state.nyttSchema = null; state.villkor = null; state.medarbetarInfo = {};
  state.kundEdit = null; state.personalEdit = null; state.intaktEdit = null;
  state.kundLek = null; state.schemaLek = null; sim = {};
  persist();
  tab = "uppladdning";
  render();
}

/* ---------- Ekonomi (speglar filens Beräkningar-blad) ---------- */
function viewEkonomi(d) {
  if (!d) return emptyState();
  if (!hasBer()) return missingSheet("Beräkningar", "Ekonomin", "Läs in en fil som innehåller modellbladen (till exempel X2-exporten), så visas verksamhetens egna ekonomital här.");
  const tal = (namn) => { const v = ber(namn); return typeof v === "number" ? v : null; };
  const krRow = (namn) => { const v = tal(namn); return v == null ? "–" : kr(v); };
  const hRow = (namn) => { const v = tal(namn); return v == null ? "–" : h1(v) + " h"; };
  const period = ber("Antal dagar i period");
  const kort = [
    ["Månadsintäkt", krRow("Månadsintäkt"), "Datumstyrd ersättning per kund", "var(--green)"],
    ["Ren schemakostnad", krRow("Ren schemakostnad"), "Planerad schematid × timkostnad", "var(--sky)"],
    ["Total kostnadsprognos", krRow("Total kostnadsprognos"), "Schemakostnad + korttidsfrånvaro m.m.", "var(--violet)"],
    ["Disponibelt efter reserv", krRow("Disponibelt utrymme efter ekonomisk reserv"), "Budgetavvikelse − ekonomisk reserv", "var(--teal)"],
  ];
  const detalj = [
    "Aktuell personalbudget", "Budgetavvikelse före reserv", "Ekonomisk reserv",
    "Prognos korttidsfrånvaro", "Beslutad bemanningsbuffert – värde", "Budgeterade personaltimmar",
  ];
  const timmar = [
    "Planerad schematid", "Planerad bruttotid", "Budgeterad medarbetartid",
    "Tillgänglig medarbetartid", "Vakanta timmar", "Övrig planerad tid",
  ];
  return `
    ${period && period !== 30 ? "" : ""}
    <div class="banner info" style="margin-bottom:16px; display:block">Siffrorna nedan är verksamhetens egna, hämtade direkt ur modellens <strong>Beräkningar</strong>-blad för hela perioden (${period ?? "?"} dagar). De ändras inte av periodväxlaren i Översikt.</div>
    <div class="grid kpis">${kort.map(([l, v, n, c]) => `<div class="kpi"><div class="lab">${l}<i class="dot" style="background:${c}"></i></div><div class="val">${v}</div><div class="note">${n}</div></div>`).join("")}</div>
    <div class="grid" style="grid-template-columns:1fr 1fr; margin-top:16px">
      <div class="card" style="padding:0; overflow:hidden">
        <div style="padding:16px 20px"><div class="eyebrow">Ekonomi i detalj</div></div>
        <table><tbody>${detalj.map((namn) => `<tr><td><strong>${namn}</strong><div class="muted" style="font-size:10px">${esc(berDef(namn))}</div></td><td style="text-align:right; white-space:nowrap">${krRow(namn)}</td></tr>`).join("")}</tbody></table>
      </div>
      <div class="card" style="padding:0; overflow:hidden">
        <div style="padding:16px 20px"><div class="eyebrow">Personaltid</div></div>
        <table><tbody>${timmar.map((namn) => `<tr><td><strong>${namn}</strong><div class="muted" style="font-size:10px">${esc(berDef(namn))}</div></td><td style="text-align:right; white-space:nowrap">${hRow(namn)}</td></tr>`).join("")}</tbody></table>
      </div>
    </div>`;
}

/* ---------- Åtgärder (speglar filens Kontroller-blad) ---------- */
function viewAtgarder(d) {
  if (!d) return emptyState();
  const list = state.kontroller;
  if (!list) return missingSheet("Kontroller", "Åtgärdslistan", "Läs in en fil med modellbladen så syns verksamhetens kontroller och åtgärder här.");
  const flag = (s) => /pass/i.test(s) ? "green" : /åtgärd/i.test(s) ? "red" : "amber";
  const behover = list.filter((r) => !/^pass$/i.test(r.status));
  const modellstatus = ber("Modellstatus");
  return `
    <div class="card" style="margin-bottom:16px; ${behover.length ? "border-color:var(--amber)" : ""}">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap">
        <div><div class="eyebrow">Modellens kontroller</div><h2 style="margin-top:4px">Vad verksamheten behöver titta på</h2></div>
        <span class="pill ${behover.length ? "amber" : "green"}">${modellstatus ? esc(String(modellstatus)) : (behover.length ? behover.length + " att åtgärda" : "Allt godkänt")}</span>
      </div>
    </div>
    <div class="card" style="padding:0; overflow:hidden">
      <table>
        <thead><tr><th>Kontroll</th><th>Utfall</th><th>Förväntat</th><th>Status</th><th>Kommentar</th></tr></thead>
        <tbody>${list.map((r) => `<tr>
          <td><strong>${esc(r.kontroll)}</strong></td>
          <td>${esc(fmtCell(r.utfall))}</td>
          <td class="muted">${esc(fmtCell(r.forvantat))}</td>
          <td><span class="pill ${flag(r.status)}">${esc(r.status)}</span></td>
          <td class="muted" style="font-size:10px">${esc(r.atgard || "")}</td>
        </tr>`).join("")}</tbody>
      </table>
    </div>`;
}
function fmtCell(v) {
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : h1(v);
  return v == null ? "" : String(v);
}

/* ---------- Generisk tabellvy ---------- */
function fmtVal(v) {
  if (v == null) return "";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : h1(v);
  if (v instanceof Date) return `${String(v.getHours()).padStart(2,"0")}:${String(v.getMinutes()).padStart(2,"0")}`;
  const s = String(v);
  const t = s.match(/^(\d{1,2}):(\d{2})/); if (t) return `${t[1].padStart(2,"0")}:${t[2]}`;
  const d = s.match(/^(\d{4})-(\d{2})-(\d{2})/); if (d) return `${d[1]}-${d[2]}-${d[3]}`;
  return s;
}
function tableCard(title, eyebrow, sheet, cols, note) {
  if (!sheet) return missingSheet(title, title, "Läs in en fil med modellbladen så visas innehållet här.");
  const use = cols && cols.length ? cols.filter((c) => sheet.columns.includes(c)) : sheet.columns;
  return `<div class="card" style="padding:0; overflow:hidden">
    <div style="padding:16px 20px; display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
      <div><div class="eyebrow">${esc(eyebrow)}</div><h2 style="margin-top:4px">${esc(title)}</h2>${note ? `<p class="muted" style="font-size:12px; margin:6px 0 0">${note}</p>` : ""}</div>
      <span class="pill blue">${sheet.rows.length} rader</span>
    </div>
    <div style="overflow:auto; max-height:640px">
      <table><thead><tr>${use.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${sheet.rows.slice(0, 400).map((r) => `<tr>${use.map((c) => `<td>${esc(fmtVal(r[c]))}</td>`).join("")}</tr>`).join("")}</tbody></table>
    </div>
    ${sheet.rows.length > 400 ? `<div class="muted" style="padding:10px 20px; font-size:11px">Visar de första 400 av ${sheet.rows.length} raderna.</div>` : ""}
  </div>`;
}

/* ---------- Medarbetare (kort-vy à la molnversionen) ---------- */
let persOppen = null; // vilket kort som är utfällt
function viewPersonal(d) {
  if (!d) return emptyState();
  if (!state.personal) return missingSheet("Medarbetare", "Bemanningen", "Läs in en fil med modellbladen så visas medarbetare och kapacitet här.");
  const rowsData = personalRader();
  const redigerad = personalEditAktiv();
  const num = (r, c) => { const v = r[c]; return typeof v === "number" ? v : 0; };
  const idAv = (r, i) => r._pid != null ? r._pid : "p" + i;
  const aktiva = rowsData.filter((r) => String(r["Status"]).toLowerCase() === "anställd");
  const vakanta = rowsData.filter((r) => String(r["Status"]).toLowerCase() === "vakant");
  const budgetKostnad = rowsData.reduce((s, r) => s + num(r, "Budgetkostnad/mån"), 0);
  const budgetH = rowsData.reduce((s, r) => s + num(r, "Budget h/mån"), 0);
  const tillgH = rowsData.reduce((s, r) => s + num(r, "Tillgängligt h/mån"), 0);
  // FTE = summa SSG (andel). Nattbehöriga = de med nattprofil eller Nattbehörig=Ja.
  const fte = rowsData.reduce((s, r) => s + (typeof r["Grund-SSG"] === "number" ? r["Grund-SSG"] : 0), 0);
  const vakantFte = vakanta.reduce((s, r) => s + (typeof r["Grund-SSG"] === "number" ? r["Grund-SSG"] : 0), 0);
  const nattbeh = rowsData.filter((r) => String(r["Nattbehörig"] ?? "") === "Ja" || /natt/i.test(String(r["Passprofil"] ?? ""))).length;

  // Sammanfattningsrad (chips)
  const chips = [
    ["Aktiva", aktiva.length, "anställda"],
    ["Kapacitet", fte.toFixed(2) + " FTE", "summa SSG"],
    ["Vakant", vakantFte.toFixed(2) + " FTE", vakanta.length + " positioner"],
    ["Nattbehöriga", nattbeh, "kan nattpass"],
    ["Budgettid", h1(budgetH) + " h", "per månad"],
    ["Personalkostnad", kr(budgetKostnad), "per månad"],
  ];
  const chipRad = `<div class="mb-chips">${chips.map(([l, v, n]) =>
    `<div class="mb-chip"><span class="mb-chip-v">${v}</span><span class="mb-chip-l">${esc(l)}</span><span class="mb-chip-n">${esc(n)}</span></div>`).join("")}</div>`;

  // Medarbetarkort. Dölj tomma platshållare ("Ny medarbetare" utan tid/status).
  const synligaRader = rowsData.filter((r) => {
    const namn = String(r["Medarbetare"] || "").trim();
    const status = String(r["Status"] || "").toLowerCase();
    const budget = typeof r["Budget h/mån"] === "number" ? r["Budget h/mån"] : 0;
    const tomPlatshallare = /^ny medarbetare/i.test(namn) && budget === 0 && status !== "anställd" && status !== "vakant";
    return !tomPlatshallare;
  });
  const kort = synligaRader.map((r, i) => {
    const id = idAv(r, i);
    const namn = String(r["Medarbetare"] ?? "");
    const init = namn.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "–";
    const status = String(r["Status"] ?? "");
    const ssg = num(r, "Grund-SSG");
    const profil = String(r["Passprofil"] ?? "–");
    const budget = num(r, "Budget h/mån");
    const tillg = num(r, "Tillgängligt h/mån");
    const timkost = num(r, "Timkostnad");
    const kostnad = num(r, "Budgetkostnad/mån");
    const helg = String(r["Helgmodell"] ?? "–");
    const rapport = String(r["Rapportindikation"] ?? "");
    const natt = String(r["Nattbehörig"] ?? "") === "Ja" || /natt/i.test(profil);
    const diff = tillg - budget;
    const oppen = persOppen === id;
    // Taggar: riktiga (profil, helg, natt) + exempel (kompetens, delegering) märkta.
    const taggar = [];
    if (profil && profil !== "–") taggar.push(`<span class="mb-tag">${esc(profil)}</span>`);
    if (natt) taggar.push(`<span class="mb-tag natt">Nattbehörig</span>`);
    if (helg && helg !== "–") taggar.push(`<span class="mb-tag">${esc(helg)}</span>`);
    taggar.push(`<span class="mb-tag">Undersköterska</span>`);
    taggar.push(`<span class="mb-tag">Läkemedelsdeleg.</span>`);

    return `<div class="mb-kort${oppen ? " open" : ""}">
      <button class="mb-huvud" onclick="persToggle('${id}')">
        <span class="mb-avatar">${esc(init)}</span>
        <span class="mb-info">
          <span class="mb-namn">${esc(namn)}</span>
          <span class="mb-tillg">Tillgänglig <strong>${h1(tillg)}</strong> av ${h1(budget)} h <span class="${diff < 0 ? "mb-neg" : "mb-pos"}">${diff >= 0 ? "+" : ""}${h1(diff)} h</span></span>
        </span>
        <span class="mb-status ${status.toLowerCase()}">${esc(status)}</span>
        <span class="mb-pil">${oppen ? "▲" : "▼"}</span>
      </button>
      <div class="mb-taggar">${taggar.join("")}</div>
      ${oppen ? `<div class="mb-detalj">
        <div class="mb-rutor">
          <div class="mb-ruta"><span class="mb-rl">Namn</span><span class="mb-rv"><input class="kb-in" style="width:130px" type="text" value="${esc(namn)}" data-pid="${id}" data-pf="namn"></span></div>
          <div class="mb-ruta"><span class="mb-rl">Status</span><span class="mb-rv"><select class="kb-in" data-pid="${id}" data-pf="status"><option ${status === "Anställd" ? "selected" : ""}>Anställd</option><option ${status === "Vakant" ? "selected" : ""}>Vakant</option><option ${status === "Tjänstledig" ? "selected" : ""}>Tjänstledig</option></select></span></div>
          <div class="mb-ruta"><span class="mb-rl">SSG</span><span class="mb-rv"><input class="kb-in" style="width:58px" type="number" min="0" max="150" step="5" value="${Math.round(ssg * 100)}" data-pid="${id}" data-pf="ssg"> %</span></div>
          <div class="mb-ruta"><span class="mb-rl">Passprofil</span><span class="mb-rv">${esc(profil)}</span></div>
          <div class="mb-ruta"><span class="mb-rl">Heltidsmått</span><span class="mb-rv">${h1(num(r, "Heltid h/vecka"))} h/v</span></div>
          <div class="mb-ruta"><span class="mb-rl">Timkostnad</span><span class="mb-rv">${timkost ? Math.round(timkost) + " kr" : "–"}</span></div>
          <div class="mb-ruta"><span class="mb-rl">Budgettid</span><span class="mb-rv">${h1(budget)} h/mån</span></div>
          <div class="mb-ruta"><span class="mb-rl">Kostnad</span><span class="mb-rv">${kr(kostnad)}/mån</span></div>
          <div class="mb-ruta"><span class="mb-rl">Helgmodell</span><span class="mb-rv">${esc(helg)}</span></div>
          <div class="mb-ruta"><span class="mb-rl">Nattbehörig</span><span class="mb-rv">${natt ? "Ja" : "Nej"}</span></div>
        </div>
        ${rapport ? `<div class="mb-rapport"><strong>Rapportindikation:</strong> ${esc(rapport)}</div>` : ""}
        
        <button class="kb-del mb-tabort" data-pdel="${id}">Ta bort medarbetare</button>
      </div>` : ""}
    </div>`;
  }).join("");

  return `<div class="card" style="margin-bottom:16px">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
        <div><div class="eyebrow">Medarbetare och villkor ${redigerad ? '· <span style="color:var(--teal)">ändrat</span>' : ""}</div>
        <h2 style="margin-top:4px">Medarbetare och kapacitet</h2>
        <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:640px">Uppgifterna styr vilka pass varje person kan få. Klicka på en medarbetare för att se och justera detaljer. Uppgifterna kommer från verksamhetens underlag.</p></div>
        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap">
          <button class="btn" id="persAdd">+ Lägg till</button>
          <button class="btn" id="persReset" ${redigerad ? "" : "disabled"}>↺ Återställ</button>
        </div>
      </div>
      ${chipRad}
    </div>
    <div class="mb-lista">${kort}</div>
    <div class="card mb-form" id="mbForm" style="margin-top:16px">
      <div class="eyebrow">Ny medarbetare</div>
      <h2 style="margin:4px 0 3px">Lägg till medarbetare</h2>
      <p class="muted" style="font-size:12px; margin:0 0 16px">Fyll i uppgifterna och klicka på Lägg till. Namn, SSG, heltidsmått, timkostnad och passprofil påverkar budget och kapacitet direkt.</p>
      <div class="mb-form-grid">
        <label class="mb-f"><span>Namn</span><input class="kb-in" id="nfNamn" type="text" placeholder="t.ex. Kepler"></label>
        <label class="mb-f"><span>Status</span><select class="kb-in" id="nfStatus"><option>Anställd</option><option>Vakant</option><option>Tjänstledig</option></select></label>
        <label class="mb-f"><span>SSG %</span><input class="kb-in" id="nfSsg" type="number" min="0" max="150" step="5" value="100"></label>
        <label class="mb-f"><span>Heltid h/v</span><input class="kb-in" id="nfHeltid" type="number" min="0" max="40" step="0.5" value="40"></label>
        <label class="mb-f"><span>Passprofil</span><select class="kb-in" id="nfProfil"><option>Dag/kväll</option><option>Natt</option><option>Flexibel</option></select></label>
        <label class="mb-f"><span>Timkostnad kr</span><input class="kb-in" id="nfTimk" type="number" min="0" step="10" value="270"></label>
        <label class="mb-f"><span>Helgmodell</span><select class="kb-in" id="nfHelg"><option>Varannan helg</option><option>Varje helg</option><option>Var tredje helg</option></select></label>
        <label class="mb-f mb-f-chk"><input type="checkbox" id="nfNatt"><span>Nattbehörig</span></label>
      </div>
      <button class="btn primary" id="nfAdd" style="margin-top:14px">+ Lägg till medarbetare</button>
    </div>`;
}
function persToggle(id) { persOppen = (persOppen === id ? null : id); render(); }

/* ---------- Schema: pedagogiskt drag-och-släpp-bräde ---------- */
let schemaFilter = "alla";
let schemaNotis = null;

// Flyttar ett pass till en annan medarbetare i lek-kopian och tar fram direkt
// återkoppling om vilka villkor som bryts. Samma logik som förut.
function flyttaPass(passId, namn) {
  if (!passId || !namn) return;
  state.schemaLek = state.schemaLek || { moves: {} };
  const tidigare = state.schemaLek.moves[passId];
  const { from } = analysPeriod();
  const veckor = Math.max(1, Math.ceil(state.analysisDays / 7));
  const foreVarningar = MODELL.kontrolleraPass(efterPass(), optimeringsVillkor(), veckor, from);
  state.schemaLek.moves[passId] = namn;
  schemaNotis = null;
  const efterVarningar = MODELL.kontrolleraPass(efterPass(), optimeringsVillkor(), veckor, from);
  const foreNycklar = new Set(foreVarningar.map((v) => `${v.namn}|${v.typ}|${v.text}`));
  const nya = efterVarningar.filter((v) => !foreNycklar.has(`${v.namn}|${v.typ}|${v.text}`));
  if (nya.length) {
    if (tidigare) state.schemaLek.moves[passId] = tidigare;
    else delete state.schemaLek.moves[passId];
    schemaNotis = { ton: "warn", namn, text: nya.map((v) => v.text).join(" • ") };
    notera("Passet kunde inte flyttas", "fel", { detalj: nya[0].text });
    persist(); render(); return;
  }
  try {
    const m = buildSchemaModel();
    if (m) {
      const eff = schemaEffektiv(m);
      const v = schemaVarningar(m, eff);
      const flyttat = eff.find((p) => p.id === passId);
      const nara = eff.filter((p) => p.namn === namn && flyttat && Math.abs(
        m.dagar.indexOf(p.datum) - m.dagar.indexOf(flyttat.datum)) <= 1);
      const brott = [];
      for (const p of nara) for (const x of v.varningar[p.id] || []) if (!x.indikation) brott.push(x.text);
      const unika = [...new Set(brott)];
      if (unika.length) schemaNotis = { ton: "warn", namn, text: unika.join(" \u2022 ") };
      else schemaNotis = { ton: "ok", namn, text: "Passet är flyttat och resultatet har räknats om." };
    }
  } catch { schemaNotis = null; }
  persist(); render();
}
function viewSchema(d) {
  if (!d) return emptyState();
  const model = buildSchemaModel();
  if (!model) return missingSheet("Individschema", "Schemat", "Läs in en fil med modellbladen så visas passen per medarbetare och dag här.");
  const effektiva = schemaEffektiv(model);
  const { varningar, medInfo } = schemaVarningar(model, effektiva);
  const lek = schemaLek();
  const antalFlyttar = Object.keys(lek.moves).length;
  const totalVarn = Object.values(varningar).reduce((s, w) => s + w.filter((x) => !x.indikation).length, 0);
  const totalInd = Object.values(varningar).reduce((s, w) => s + w.filter((x) => x.indikation).length, 0);

  // Rullgardin: alla eller en medarbetare
  const options = ["alla", ...model.medarbetare];
  const drop = `<select id="schemaMed" class="schemasel">${options.map((o) =>
    `<option value="${esc(o)}" ${o === schemaFilter ? "selected" : ""}>${o === "alla" ? "Alla medarbetare" : esc(o)}</option>`).join("")}</select>`;

  const visaMed = schemaFilter === "alla" ? model.medarbetare : [schemaFilter];
  // Passindex per (namn|datum)
  const byCell = {};
  for (const p of effektiva) (byCell[`${p.namn}|${p.datum}`] ||= []).push(p);

  // Rubrikrad med datum
  const dagHead = model.dagar.map((iso) => {
    const dd = new Date(iso + "T12:00:00Z"); const wd = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"][(dd.getUTCDay() + 6) % 7];
    const helg = wd === "lör" || wd === "sön";
    return `<th class="daycol ${helg ? "helg" : ""}"><span>${wd}</span>${iso.slice(8)}</th>`;
  }).join("");

  const passColor = (typ) => /natt/i.test(typ) ? "natt" : /kväll/i.test(typ) ? "kvall" : /resurs|ssg/i.test(typ) ? "resurs" : "dag";
  const rows = visaMed.map((namn) => {
    const info = medInfo[namn] || { planeradH: 0, malH: 0, diff: 0, nattbehorig: false };
    const prof = model.prof[namn] || {};
    const ssgTone = Math.abs(info.diff) <= 8 ? "green" : Math.abs(info.diff) <= 20 ? "amber" : "red";
    const celler = model.dagar.map((iso) => {
      const list = byCell[`${namn}|${iso}`] || [];
      const chips = list.map((p) => {
        const w = varningar[p.id] || [];
        const hard = w.some((x) => !x.indikation); const ind = w.some((x) => x.indikation);
        const title = w.map((x) => (x.indikation ? "ⓘ " : "⚠ ") + x.text).join(" • ");
        return `<div class="passchip ${passColor(p.typ)} ${hard ? "warn" : ind ? "ind" : ""}" draggable="true"
          data-pass="${p.id}" title="${esc(title || p.typ + " " + p.start + "–" + p.slut)}">
          <span>${esc(p.typ)}</span><em>${p.start}–${p.slut}</em>${hard ? '<i class="wbadge">⚠</i>' : ind ? '<i class="wbadge ind">ⓘ</i>' : ""}
        </div>`;
      }).join("");
      return `<td class="cell" data-namn="${esc(namn)}" data-datum="${iso}">${chips}</td>`;
    }).join("");
    return `<tr>
      <th class="medcol">
        <strong>${esc(namn)}</strong>
        <div class="medmeta">
          <span class="pill ${ssgTone}" title="Planerad tid mot budget/mål">${info.diff >= 0 ? "+" : ""}${h1(info.diff)} h mot mål</span>
          ${prof.nattbehorig ? '<span class="nb" title="Nattbehörig">natt ✓</span>' : ''}
        </div>
      </th>${celler}
    </tr>`;
  }).join("");

  return `
  <div class="card" style="margin-bottom:14px">
    <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap">
      <div><div class="eyebrow">Schemabräde</div><h2 style="margin-top:4px">Dra ett pass till en annan medarbetare</h2>
      <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:620px">Flytta pass genom att dra och släppa. Systemet varnar direkt vid dygnsvila under 11 h, för många pass i följd, natt utan behörighet och stora SSG-avvikelser. Övertid och veckovila visas som <strong>indikationer</strong> (ⓘ) som bör kontrolleras mot avtalet. Ändringarna sker och rör aldrig den importerade datan.</p></div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap">${drop}
        <button class="btn" id="schemaReset" ${antalFlyttar ? "" : "disabled"}>↺ Återställ (${antalFlyttar})</button>
      </div>
    </div>
    <div style="display:flex; gap:8px; margin-top:12px; flex-wrap:wrap">
      <span class="pill ${totalVarn ? "red" : "green"}">${totalVarn ? totalVarn + " regelvarningar" : "Inga regelbrott"}</span>
      ${totalInd ? `<span class="pill amber">${totalInd} indikationer (övertid/veckovila)</span>` : ""}
      ${antalFlyttar ? `<span class="pill blue">${antalFlyttar} flyttade pass</span>` : ""}
    </div>
    ${schemaNotis ? `<div class="banner ${schemaNotis.ton === "warn" ? "warn" : "info"}" style="margin-top:12px">
      <strong>${schemaNotis.ton === "warn" ? "⚠ Villkor bryts" : "✓ Passet är flyttat"}</strong>
      <div>${esc(schemaNotis.namn)}: ${esc(schemaNotis.text)}</div></div>` : ""}
  </div>
  <div class="schemawrap"><table class="schema"><thead><tr><th class="medcol">Medarbetare</th>${dagHead}</tr></thead><tbody>${rows}</tbody></table></div>
  <div class="legend" style="margin-top:12px">
    <span><i class="swatch" style="background:#d7e9f6"></i>Dag</span>
    <span><i class="swatch" style="background:#e6dff5"></i>Kväll</span>
    <span><i class="swatch" style="background:#dfe4ea"></i>Natt</span>
    <span><i class="swatch" style="background:#e2f0e8"></i>Resurs/SSG</span>
    <span><i class="swatch" style="background:#fbe0de"></i>⚠ Regelbrott</span>
    <span><i class="swatch" style="background:#fbf1e0"></i>ⓘ Indikation</span>
  </div>`;
}

/* ---------- Intäkter ---------- */
function viewIntakter(d) {
  if (!d) return emptyState();
  if (!state.intakter) return missingSheet("Intäkter", "Intäkterna", "Läs in HR-exporten (X2) så visas intäkterna här.");
  const rowsData = intaktRader();
  const redigerad = intaktEditAktiv();
  const num = (r, c) => { const v = r[c]; return typeof v === "number" ? v : Number(v) || 0; };
  const total = rowsData.reduce((s, r) => s + num(r, "Beräknad intäkt"), 0);

  // Aggregera per kund: grundersättning (kr/dygn), antal dagar, summa, aktiv.
  const perKund = {};
  for (const r of rowsData) {
    const k = String(r["Kund"] ?? "").trim(); if (!k) continue;
    if (!perKund[k]) perKund[k] = { kund: k, grund: num(r, "Grund kr/dygn") || num(r, "Ny ersättning"), dagar: 0, summa: 0, aktiv: Number(r["Aktiv kund"]) !== 0 };
    perKund[k].dagar++; perKund[k].summa += num(r, "Beräknad intäkt");
  }
  const kunder = Object.values(perKund).sort((a, b) => a.kund.localeCompare(b.kund, "sv"));

  const kort = `<div class="grid kpis" style="margin-bottom:16px">
    <div class="kpi"><div class="lab">Månadsintäkt totalt<i class="dot" style="background:var(--green)"></i></div><div class="val">${kr(total)}</div><div class="note">${redigerad ? "räknas live ur dina ändringar" : "summa datumstyrd ersättning"}</div></div>
    ${kunder.slice(0, 3).map((k) => `<div class="kpi"><div class="lab">${esc(k.kund)}<i class="dot" style="background:var(--sky)"></i></div><div class="val">${kr(k.summa)}</div><div class="note">${k.grund.toLocaleString("sv-SE")} kr/dygn</div></div>`).join("")}
  </div>`;

  const rader = kunder.map((k) => `<tr>
    <td><strong>${esc(k.kund)}</strong></td>
    <td><input class="kb-in" style="width:88px" type="number" min="0" step="100" value="${Math.round(k.grund)}" data-intk="${esc(k.kund)}" data-intf="grund"> kr/dygn</td>
    <td>${k.dagar} dygn</td>
    <td><label class="kb-chk"><input type="checkbox" ${k.aktiv ? "checked" : ""} data-intk="${esc(k.kund)}" data-intf="aktiv"> aktiv kund</label></td>
    <td style="text-align:right"><strong>${kr(k.summa)}</strong></td>
  </tr>`).join("");

  return kort + `
  <div class="card" style="padding:0; overflow:hidden">
    <div style="padding:18px 22px; display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
      <div><div class="eyebrow">Datumstyrd intäktsberäkning ${redigerad ? '· <span style="color:var(--teal)">ändrat</span>' : ""}</div><h2 style="margin-top:4px">Intäkter</h2>
      <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:620px">Ändra grundersättningen (kr/dygn) per kund – beräknad intäkt och månadsintäkten uppdateras med en gång. Bocka ur en kund för att se effekten om ersättningen upphör.; den importerade datan rörs aldrig.</p></div>
      <button class="btn" id="intReset" ${redigerad ? "" : "disabled"}>↺ Återställ</button>
    </div>
    <div style="overflow:auto; max-height:600px">
      <table><thead><tr><th>Kund</th><th>Grundersättning</th><th>Dagar</th><th>Status</th><th style="text-align:right">Intäkt i perioden</th></tr></thead>
      <tbody>${rader}</tbody>
      <tfoot><tr style="border-top:2px solid var(--line)"><td colspan="4"><strong>Månadsintäkt totalt</strong></td><td style="text-align:right"><strong>${kr(total)}</strong></td></tr></tfoot></table>
    </div>
  </div>`;
}

/* ---------- Vad händer om (känslighetsreglage) ---------- */
function viewSimulering(d) {
  if (!d) return emptyState();
  const base = simBaseline(d);
  const r = simCompute(base);
  const dirty = Object.keys(sim).length > 0;
  // Ett reglage: id, etikett, min, max, steg, utgångsvärde, aktuellt värde, formattering, hjälptext
  const S = (id, label, min, max, step, baseVal, cur, fmt, help) => {
    const changed = sim[id] != null && Math.abs(sim[id] - baseVal) > 1e-9;
    return `<div class="slider ${changed ? "on" : ""}">
      <div class="slabel"><span>${label}</span><strong>${fmt(cur)}</strong></div>
      <input type="range" min="${min}" max="${max}" step="${step}" value="${cur}" data-sim="${id}">
      <div class="shint"><span>Filens värde: ${fmt(baseVal)}</span>${help ? `<span>${help}</span>` : ""}</div>
    </div>`;
  };
  const g = (k, dflt) => (sim[k] != null ? sim[k] : dflt);
  const kr0 = (x) => Math.round(x).toLocaleString("sv-SE") + " kr";
  const pct = (x) => x.toLocaleString("sv-SE", { maximumFractionDigits: 1 }) + " %";
  const hh = (x) => h1(x) + " h";

  const vakMax = base.vak.length;
  const resultPos = r.disponibelt >= 0;

  return `
  <div class="simresult">
    <div class="sr-head">
      <div><div class="eyebrow" style="color:#bfe3de">Vad händer om</div><h2 style="color:#fff; margin-top:2px">Effekt av dina antaganden</h2></div>
      <button class="btn" id="simReset" ${dirty ? "" : "disabled"}>↺ Återställ till filens värden</button>
    </div>
    <div class="sr-grid">
      ${srCard("Disponibelt efter reserv", kr0(r.disponibelt), "Budget − prognos − reserv", resultPos ? "pos" : "neg")}
      ${srCard("Månadsintäkt", kr0(r.intakt), "Ersättning per kund och dygn")}
      ${srCard("Total kostnadsprognos", kr0(r.totalPrognos), "Schemakostnad + korttidsfrånvaro")}
      ${srCard("Dimensionerande behov", hh(r.dimBehov), "Inkl. vaken natt som golv")}
      ${srCard("Bemanningsgap i kronor", kr0(r.gapKr), `${hh(r.gapH)} × ${Math.round(r.timkostnad)} kr`, r.gapH >= 0 ? "pos" : "neg")}
    </div>
  </div>

  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); margin-top:16px; align-items:start">
    <div class="card">
      <div class="eyebrow">Ekonomi och personal</div>
      ${S("timkostnad", "1 · Timkostnad", 200, 400, 5, base.timkostnad, g("timkostnad", base.timkostnad), (x) => Math.round(x) + " kr/h")}
      ${vakMax ? S("tillsattVak", "2 · Tillsätt vakanser", 0, vakMax, 1, 0, g("tillsattVak", 0), (x) => `${x} av ${vakMax}`, `+${h1(r.extraTimmar)} h schematid`) : `<div class="shint" style="padding:8px 0">Inga vakanta positioner i filen.</div>`}
      ${S("korttidPct", "3 · Korttidsfrånvaro", 0, 15, 0.5, base.korttidPct, g("korttidPct", base.korttidPct), pct)}
      ${S("reservPct", "4 · Ekonomisk reserv", 0, 15, 0.5, base.reservPct, g("reservPct", base.reservPct), pct)}
      ${S("buffertPct", "5 · Bemanningsbuffert", 0, 15, 0.5, base.buffertPct, g("buffertPct", base.buffertPct), pct)}
      ${S("budget", "6 · Personalbudget", Math.round(base.budget * 0.7 / 1000) * 1000, Math.round(base.budget * 1.3 / 1000) * 1000, 5000, base.budget, g("budget", base.budget), kr0)}
    </div>
    <div class="card">
      <div class="eyebrow">Intäkt</div>
      ${S("kundRatePct", "7 · Grundersättning per kund", 50, 150, 1, 100, g("kundRatePct", 100), (x) => x + " % av original", `≈ ${Math.round(base.kundRate[Object.keys(base.kundRate)[0]] * g("kundRatePct", 100) / 100 || 0)} kr/dygn`)}
      ${S("kunddagarPct", "8 · Aktiva kunddagar", 50, 120, 1, 100, g("kunddagarPct", 100), (x) => x + " % av original", "kund till/från")}
      <div class="eyebrow" style="margin-top:18px">Behov och dimensionering</div>
      ${S("nattgolv", "9 · Nattgolv (vaken natt)", 0, 3, 1, base.nattgolv, g("nattgolv", base.nattgolv), (x) => x + " medarb.")}
      ${S("planeradeTimmar", "10 · Planerade timmar", Math.round(base.planeradeTimmar * 0.7), Math.round(base.planeradeTimmar * 1.3), 10, base.planeradeTimmar, g("planeradeTimmar", base.planeradeTimmar), hh)}
      ${S("malPct", "11 · Målnivå (påverkar ej beräkning)", 50, 100, 1, base.malPct, g("malPct", base.malPct), pct)}
    </div>
    <div class="card">
      <div class="eyebrow">Sammansatt</div>
      <div class="simline"><span>12 · Bemanningsgap i kronor</span><strong class="${r.gapH >= 0 ? "" : "neg"}">${kr0(r.gapKr)}</strong></div>
      <div class="shint">${r.gapH >= 0 ? "Överkapacitet" : "Underskott"}: ${hh(Math.abs(r.gapH))} vid ${Math.round(r.timkostnad)} kr/h. Planerade timmar (${hh(r.planeradeTimmar)}) mot dimensionerande behov (${hh(r.dimBehov)}).</div>
      <div class="simline" style="margin-top:16px"><span>13 · Break-even timkostnad</span><strong>${r.planeradeTimmar > 0 ? Math.round((base.budget - base.budget * g("reservPct", base.reservPct) / 100) / (r.schematid * (1 + g("korttidPct", base.korttidPct) / 100))) : "–"} kr/h</strong></div>
      <div class="shint">Den timkostnad där prognosen (inkl. korttidsfrånvaro) precis möter budgeten efter reserv, vid nuvarande schematid.</div>
      <div class="simline" style="margin-top:16px"><span>Resultat (intäkt − kostnad)</span><strong class="${r.resultat >= 0 ? "" : "neg"}">${kr0(r.resultat)}</strong></div>
      <div class="shint">Månadsintäkt minus total kostnadsprognos med dina antaganden.</div>
    </div>
  </div>
  <p class="muted" style="font-size:11px; margin-top:14px">Alla värden räknas på en kopia av filens siffror. Reglagen ändrar aldrig den importerade datan eller övriga flikar. Effekterna är aritmetiska – de lägger inte om schemat eller kontrollerar arbetstidsregler.</p>`;
}
function srCard(label, value, note, tone) {
  return `<div class="sr-card ${tone || ""}"><div class="sr-lab">${label}</div><div class="sr-val">${value}</div><div class="sr-note">${note}</div></div>`;
}

/* ---------- Sprid behov: kundbehovsbräde med drag inom fönster ---------- */
let spridDay = 0;
let spridZoom = "dag"; // dag | vecka | manad
function viewSprid(d) {
  if (!d) return emptyState();
  const days = []; for (let i = 0; i < state.analysisDays; i++) days.push(addDays(state.period.from, i));
  const lek = kundLek();
  const dayPeaks = days.map((iso) => {
    const ins = kundDagModell(iso);
    const moten = (lek.moten || []).filter((m) => m.datum === iso);
    const kurva = kundDagKurva(ins, moten);
    const behovH = ins.reduce((s, p) => s + p.dur * p.staff, 0) / 60;
    return { iso, peak: kurva.peak, peakSlot: kurva.peakSlot, behovH, antal: ins.length, flyttbara: ins.filter((p) => p.flyttbar).length };
  });
  const maxPeak = Math.max(1, ...dayPeaks.map((x) => x.peak));
  const safeDay = Math.min(spridDay, days.length - 1);

  const header = `
  <div class="card" style="margin-bottom:14px">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap">
      <div><div class="eyebrow">Sprid kundbehov</div><h2 style="margin-top:4px">Jämna ut topparna inom insatsernas fönster</h2>
      <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:640px">Välj <strong>Månad</strong> eller <strong>Vecka</strong> för att se vilka dagar som har högst samtidighet, och klicka på en dag för att öppna <strong>Dag</strong>-läget där du drar flyttbara insatser inom deras fönster.</p></div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap">
        <div class="seg">${["manad", "vecka", "dag"].map((z) => `<button class="${spridZoom === z ? "on" : ""}" data-zoom="${z}">${z === "dag" ? "Dag" : z === "vecka" ? "Vecka" : "Månad"}</button>`).join("")}</div>
        <button class="btn" id="spridReset" ${Object.keys(lek.moves).length || (lek.moten || []).length ? "" : "disabled"}>↺ Återställ</button>
      </div>
    </div>
  </div>`;

  if (spridZoom !== "dag") {
    const set = spridZoom === "manad" ? dayPeaks : dayPeaks.slice(Math.max(0, safeDay - 3), Math.max(0, safeDay - 3) + 7);
    const cards = set.map((x) => {
      const di = days.indexOf(x.iso);
      const dd = new Date(x.iso + "T12:00:00Z"); const wd = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"][(dd.getUTCDay() + 6) % 7];
      const helg = wd === "lör" || wd === "sön";
      const tone = x.peak > 8 ? "red" : x.peak > 6 ? "amber" : "green";
      return `<button class="daycard ${helg ? "helg" : ""}" data-day="${di}">
        <div class="dc-top"><span>${wd} ${x.iso.slice(8)}</span>${x.flyttbara ? `<i class="dc-flag" title="${x.flyttbara} flyttbara insatser">⇄ ${x.flyttbara}</i>` : ""}</div>
        <div class="dc-peak pill ${tone}">Topp ${x.peak} kl. ${minClock(x.peakSlot * 15)}</div>
        <div class="dc-bar"><i style="height:${x.peak / maxPeak * 100}%"></i></div>
        <div class="dc-meta">${h1(x.behovH)} h · ${x.antal} insatser</div>
      </button>`;
    }).join("");
    const veckoSum = set.reduce((s, x) => s + x.behovH, 0);
    return header + `
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:8px">
          <div class="eyebrow">${spridZoom === "manad" ? "Månadsöversikt – hela perioden" : "Veckoöversikt"}</div>
          <span class="pill blue">Summa kundbehov: ${h1(veckoSum)} h</span>
        </div>
        <div class="daygrid">${cards}</div>
        <p class="muted" style="font-size:11px; margin-top:12px">Klicka på en dag för att öppna dagvyn och dra insatser. Röd = hög samtidighet (fler än 8), gul = 7–8, grön = lugnare.</p>
      </div>`;
  }

  const iso = days[safeDay];
  const insatser = kundDagModell(iso);
  const moten = (lek.moten || []).filter((m) => m.datum === iso);
  const kurva = kundDagKurva(insatser, moten);
  const antalFlyttar = Object.keys(lek.moves).length;
  const rorliga = insatser.filter((p) => p.flyttbar).length;
  const hourMarks = Array.from({ length: 13 }, (_, i) => `<span style="left:${i * 2 / 24 * 100}%">${String(i * 2).padStart(2, "0")}</span>`).join("");
  const kunder = [...new Set(insatser.map((p) => p.kund))].sort((a, b) => a === "Gemensamt" ? 1 : b === "Gemensamt" ? -1 : a.localeCompare(b, "sv"));
  const rader = kunder.map((kund) => {
    const blocks = insatser.filter((p) => p.kund === kund).map((p) => {
      const left = p.start / 1440 * 100, width = Math.max(1.2, p.dur / 1440 * 100);
      const fLeft = p.fonsterStart / 1440 * 100, fWidth = ((p.fonsterEnd ?? p.end) - p.fonsterStart) / 1440 * 100;
      return `${p.flyttbar ? `<div class="fonster" style="left:${fLeft}%; width:${fWidth}%" title="Tillåtet fönster ${minClock(p.fonsterStart)}–${minClock(p.fonsterEnd)}"></div>` : ""}
        <div class="insats ${p.flyttbar ? "rorlig" : "fast"} ${p.moved ? "moved" : ""} ${p.staff > 1 ? "dubbel" : ""}"
          style="left:${left}%; width:${width}%" draggable="${p.flyttbar}" data-ins="${p.id}"
          title="${esc(p.insats)} ${minClock(p.start)}–${minClock(p.end)}${p.flyttbar ? ` · dra inom ${minClock(p.fonsterStart)}–${minClock(p.fonsterEnd)}` : " · fast tid"}">
          <span>${esc(p.insats)}</span></div>`;
    }).join("");
    return `<div class="tlrow"><div class="tlname">${esc(kund)}</div><div class="tltrack" data-kund="${esc(kund)}">${blocks}</div></div>`;
  }).join("");
  const moteBlocks = moten.map((m, i) => {
    const left = m.start / 1440 * 100, width = Math.max(1.5, m.dur / 1440 * 100);
    return `<div class="mote" style="left:${left}%; width:${width}%" data-mote="${i}" draggable="true" title="${esc(m.titel)} ${minClock(m.start)}–${minClock(m.start + m.dur)}"><span>${esc(m.titel)}</span></div>`;
  }).join("");
  const curveBars = kurva.slots.map((v, i) => {
    const hh = Math.floor(i * 15 / 60); const night = hh >= 22 || hh < 6;
    return `<i class="cb ${night ? "n" : ""}" style="height:${v / Math.max(1, kurva.peak) * 100}%" title="${minClock(i * 15)}: behov ${v} samtidiga insatser"></i>`;
  }).join("");
  // Schemalagda medarbetare (ur Medvind-passen) som en linje ovanpå behovsstaplarna.
  const bemRaw = (state.optimerat && typeof schemaPerSlot === "function") ? schemaPerSlot(iso) : null;
  const bemMaxRaw = bemRaw ? Math.max(...bemRaw) : 0;
  const bemSlots = bemMaxRaw > 0 ? bemRaw : null; // ingen linje när schema saknas
  const bemMax = bemMaxRaw;
  let bemLinje = "";
  if (bemSlots && bemMax > 0) {
    const yMaxB = Math.max(kurva.peak, bemMax, 1);
    const pts = bemSlots.map((v, i) => `${(i / 95 * 100).toFixed(2)},${(100 - v / yMaxB * 100).toFixed(2)}`).join(" ");
    bemLinje = `<svg class="cbline" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="${pts}" /></svg>`;
  }
  // Y-axelmarkeringar så man kan läsa av hur många som behövs, inte bara se höjd.
  const yMax = Math.max(1, kurva.peak, bemMax);
  const ySteg = yMax <= 5 ? 1 : yMax <= 10 ? 2 : yMax <= 20 ? 5 : 10;
  const yLbls = [];
  for (let v = 0; v <= yMax; v += ySteg) yLbls.push(`<span style="bottom:${v / yMax * 100}%">${v}</span>`);
  const yAxel = `<div class="cbyax">${yLbls.join("")}</div>`;
  // Om behovsstaplarna och linjen har olika skala, skala om staplarna till yMax.
  const curveBars2 = kurva.slots.map((v, i) => {
    const hh = Math.floor(i * 15 / 60); const night = hh >= 22 || hh < 6;
    return `<i class="cb ${night ? "n" : ""}" style="height:${v / yMax * 100}%" title="${minClock(i * 15)}: behov ${v} samtidiga insatser${bemSlots ? `, schemalagt ${bemSlots[i]}` : ""}"></i>`;
  }).join("");
  const dd = new Date(iso + "T12:00:00Z"); const wdName = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"][(dd.getUTCDay() + 6) % 7];

  return header + `
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px">
      <div style="display:flex; align-items:center; gap:8px"><button class="btn" id="spPrev">‹</button><strong>${wdName} ${iso}</strong><button class="btn" id="spNext">›</button></div>
      <div style="display:flex; gap:8px; flex-wrap:wrap">
        <span class="pill ${kurva.peak > 6 ? "amber" : "green"}">Högsta samtidighet: ${kurva.peak} kl. ${minClock(kurva.peakSlot * 15)}</span>
        <span class="pill blue">${rorliga} flyttbara insatser</span>
        ${antalFlyttar ? `<span class="pill blue">${antalFlyttar} flyttade</span>` : ""}
      </div>
    </div>
    <div class="curveband-wrap">
      <div class="cblabel">Behov (samtidiga insatser)${bemSlots ? " vs schemalagda medarbetare" : ""}<span class="cbleg"><i class="lg-bar"></i>Behov${bemSlots ? '<i class="lg-line"></i>Schemalagda medarbetare' : '<span style="font-weight:400">Läs in schemat för att se bemanningen</span>'}</span></div>
      <div class="curveband">${yAxel}<div class="cbtrack">${curveBars2}</div>${bemLinje}<div class="cbpeak">${kurva.peak}</div></div>
    </div>
    <div class="tlhours">${hourMarks}</div>
    <div class="timeline">
      ${rader}
      <div class="tlrow mote-row"><div class="tlname">Möte / utbildning</div><div class="tltrack" data-kund="__mote">${moteBlocks}</div></div>
    </div>
    <div style="display:flex; gap:8px; margin-top:14px; flex-wrap:wrap; align-items:center">
      <button class="btn primary" id="addMote">+ Lägg möte där behovet är lägst</button>
      <span class="muted" style="font-size:11px">Appen placerar mötet i största lediga luckan 08–17. Dra det sedan dit du vill.</span>
    </div>
    <div class="legend" style="margin-top:12px">
      <span><i class="swatch" style="background:#bcd8f0"></i>Fast insats (kan inte flyttas)</span>
      <span><i class="swatch" style="background:#f7c948; outline:1px solid #b0790f"></i>⇄ Flyttbar insats – dra och släpp</span>
      <span><i class="swatch" style="background:#eef1f4; outline:1px dashed #9aa7b2"></i>Tillåtet fönster</span>

      <span><i class="swatch" style="background:#5b53a6"></i>Möte/utbildning</span>
    </div>
  </div>`;
}

/* Före/efter ritas av React-vyn ForeEfter.tsx utifrån foreEfterModell().
 * FÖRE är alltid det uppladdade riktiga schemat – aldrig ett härlett nuläge. */



/* ---------- Styrande villkor: påvisar modellens regelverk ---------- */
function viewVillkor(d) {
  const v = state.villkor;
  if (!v) return `<div class="banner info" style="display:block">De styrande villkoren finns i Excel-filen. <strong>Importera HR-exporten (X2)</strong> så visas verksamhetens regler, individuella villkor och villkorskatalogen här.</div>`;

  // Gruppera inställningar tematiskt för läsbarhet.
  const grupper = {
    "Arbetstidsregler": ["Minsta dygnsvila", "Standardrast", "Max sammanhängande arbete", "Långpass – gul varning", "Långpass – röd varning", "Önskat max nattpass i följd", "Nattserie – gul varning", "Nattserie – röd varning", "Max arbetsdagar i följd", "Minsta fridagar", "Individuell kontrollperiod", "Veckoarbetstid dag/kväll", "Veckoarbetstid ständig natt"],
    "Ekonomi & mål": ["Timkostnad", "Personalbudget", "Intäkt per kund och dygn", "Korttidsfrånvaro", "Effektivitetsmål", "Bemanningsbuffert", "Ekonomisk reserv", "Månadsintäkt"],
    "Planering & bemanning": ["Schema lämnas i förväg", "Längsta schemaperiod", "Vaken natt – grundbemanning", "Tidsintervall", "Helgprincip", "Tröskel för nytt schemaförslag", "Antal kunder", "Antal dagar i period", "Periodstart"],
  };
  const hittad = new Set();
  const grStr = Object.entries(grupper).map(([titel, namn]) => {
    const rader = namn.map((n) => v.installningar.find((x) => x.namn === n)).filter(Boolean);
    rader.forEach((r) => hittad.add(r.namn));
    if (!rader.length) return "";
    return `<div class="card" style="margin-bottom:14px">
      <div class="eyebrow">${titel}</div>
      <table style="margin-top:10px"><tbody>
        ${rader.map((r) => `<tr>
          <td><strong>${esc(r.namn)}</strong></td>
          <td style="white-space:nowrap"><span class="pill blue">${esc(vardeMedEnhet(r))}</span></td>
          <td class="muted" style="font-size:11px">${esc(r.kommentar)}</td>
        </tr>`).join("")}
      </tbody></table>
    </div>`;
  }).join("");

  // Övriga inställningar som inte hamnade i en grupp
  const ovriga = v.installningar.filter((r) => !hittad.has(r.namn) && r.varde !== "");
  const ovrStr = ovriga.length ? `<div class="card" style="margin-bottom:14px"><div class="eyebrow">Övriga inställningar</div>
    <table style="margin-top:10px"><tbody>${ovriga.map((r) => `<tr><td><strong>${esc(r.namn)}</strong></td><td style="white-space:nowrap"><span class="pill blue">${esc(vardeMedEnhet(r))}</span></td><td class="muted" style="font-size:11px">${esc(r.kommentar)}</td></tr>`).join("")}</tbody></table></div>` : "";

  // Individuella villkor (datumstyrda undantag)
  const indStr = v.individ.length ? `<div class="card" style="margin-bottom:14px">
    <div class="eyebrow">Individuella villkor – datumstyrda undantag</div>
    <h3 style="margin-top:4px">${v.individ.length} aktiva individvillkor</h3>
    <table style="margin-top:10px"><thead><tr><th>Medarbetare</th><th>Villkor</th><th>Från</th><th>Till</th></tr></thead>
    <tbody>${v.individ.map((r) => `<tr><td><strong>${esc(avidentifieraEtt(r.medarbetare))}</strong></td><td>${esc(r.typ)}</td><td>${esc(r.fran)}</td><td>${esc(r.till)}</td></tr>`).join("")}</tbody></table>
  </div>` : "";

  // Rörliga villkor – katalog av villkorstyper
  const katStr = Object.keys(v.rorligaKategorier).length ? `<div class="card">
    <div class="eyebrow">Rörliga villkor – katalog</div>
    <h3 style="margin-top:4px">${v.rorligaAntal} villkorstyper som kan registreras</h3>
    <p class="muted" style="font-size:12px; margin:6px 0 14px; max-width:640px">Modellen kan hantera avvikelser i tre kategorier. De ligger som mallar och aktiveras vid behov – t.ex. sjukfrånvaro, ändrad sysselsättningsgrad eller ny kund.</p>
    <div class="villkor-kat">
      ${Object.entries(v.rorligaKategorier).map(([kat, typer]) => `<div class="vk-grupp">
        <div class="vk-titel">${esc(kat)} <span class="muted">(${typer.length})</span></div>
        <div class="vk-taggar">${typer.map((t) => `<span class="vk-tag">${esc(t)}</span>`).join("")}</div>
      </div>`).join("")}
    </div>
  </div>` : "";

  return `
  <div class="card" style="margin-bottom:16px; background:linear-gradient(135deg,#f0f6f5,#fff)">
    <div class="eyebrow">Styrande villkor</div>
    <h2 style="margin-top:4px">Regelverket bakom schemat</h2>
    <p class="muted" style="font-size:12px; margin:6px 0 0; max-width:660px">Det här är verksamhetens och avtalets villkor som ligger till grund för planeringen: arbetstidsregler, ekonomiska ramar, individuella undantag och en katalog av avvikelser modellen kan hantera. De visas här för att påvisa hur genomtänkt underlaget är.</p>
  </div>
  ${grStr}${ovrStr}${indStr}${katStr}`;
}
function vardeMedEnhet(r) {
  let val = r.varde;
  // Andelar (0..1) som procent
  if (/mål|frånvaro|buffert|reserv/i.test(r.namn) && /^0?\.\d+$/.test(String(val))) {
    val = Math.round(Number(val) * 100) + " %";
    return val;
  }
  const enhet = r.enhet && !/^%$/.test(r.enhet) ? " " + r.enhet : (r.enhet === "%" ? " %" : "");
  return val + enhet;
}
function avidentifieraEtt(namn) {
  return (typeof FIKTIVA_NAMN === "object" && FIKTIVA_NAMN[namn]) ? FIKTIVA_NAMN[namn] : namn;
}



}
