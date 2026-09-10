// @ts-nocheck
/* Ported verbatim from the original Bemanningsbalans calculation core.
   Logic and formulas are unchanged. */
/**
 * Bemanningsbalans – beräkningskärna (rättad enligt kravspecifikation 2026-07)
 *
 * Ren beräkningsmodul utan UI-beroenden. Alla resultat beräknas från rådata –
 * inga hårdkodade totalsummor. Kan användas i webbläsare eller Node.
 *
 * Insatsrad (normaliserad):
 * { id, datum: "YYYY-MM-DD", kund, insats, start: "HH:MM", slut: "HH:MM",
 *   fonsterSlut: "HH:MM"|null, minuter: number, tvaPersoner: bool,
 *   flyttbar: bool, status: "Utförd"|"Ej utförd"|"Inställd"|"Flyttad", kallrad }
 */

// ---------- Hjälpfunktioner ----------

export function normKund(s) {
  // Normalisera dubbla och avslutande mellanslag. Byt ALDRIG kund utifrån
  // sorteringsordning, radnummer eller antal insatser.
  return String(s == null ? "" : s).replace(/\s+/g, " ").trim();
}

export function toMin(hhmm) {
  if (hhmm == null) return null;
  const [h, m] = String(hhmm).split(":").map(Number);
  return h * 60 + m;
}

/** Stabilt rad-ID av datum, starttid, sluttid, kund, insats och källrad. */
export function stabiltId(rad) {
  const key = [rad.datum, rad.start, rad.slut || "", normKund(rad.kund), rad.insats, String(rad.kallrad)].join("|");
  let h1 = 0x811c9dc5, h2 = 0x01000193; // FNV-varianter, deterministiskt
  for (let i = 0; i < key.length; i++) {
    h1 = (h1 ^ key.charCodeAt(i)) >>> 0; h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = (h2 + key.charCodeAt(i) * (i + 1)) >>> 0;
  }
  return h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0");
}

/** Filtrera på vald period (inklusive gränser). Blanda aldrig perioder. */
export function filtreraPeriod(rader, fran, till) {
  return rader.filter(r => r.datum >= fran && r.datum <= till);
}

// ---------- Grundberäkning per insats ----------

export function berikaInsats(r) {
  // Kundbehov = värdet i Minuter. Korta insatser (2/5/10 min) behåller sin
  // faktiska tid – ingen avrundning till 15 eller 30 minuter.
  const antalMedarbetare = r.tvaPersoner ? 2 : 1;
  const kundbehovMin = r.minuter;
  const personalbehovMin = r.minuter * antalMedarbetare;
  return {
    ...r,
    kund: normKund(r.kund),
    antalMedarbetare,
    kundbehovMin,
    personalbehovMin,
    extraDubbelMin: personalbehovMin - kundbehovMin,
  };
}

// ---------- Nyckeltal och kundsammanställning ----------

export function nyckeltal(rader) {
  // Status tar INTE bort en insats ur planerat kundbehov; status används
  // endast vid uppföljning av utfallet.
  const b = rader.map(berikaInsats);
  const sum = (f) => b.reduce((a, r) => a + f(r), 0);
  return {
    antalInsatser: b.length,
    kundbehovH: sum(r => r.kundbehovMin) / 60,
    fastBehovH: sum(r => (r.flyttbar ? 0 : r.kundbehovMin)) / 60,
    flyttbartBehovH: sum(r => (r.flyttbar ? r.kundbehovMin : 0)) / 60,
    personalbehovH: sum(r => r.personalbehovMin) / 60,
    extraDubbelH: sum(r => r.extraDubbelMin) / 60,
    dubbelbemannadeRader: b.filter(r => r.antalMedarbetare === 2).length,
  };
}

export function perKund(rader) {
  const m = new Map();
  for (const r of rader.map(berikaInsats)) {
    if (!m.has(r.kund)) m.set(r.kund, { kund: r.kund, insatser: 0, kundbehovH: 0, personalbehovH: 0 });
    const k = m.get(r.kund);
    k.insatser += 1;
    k.kundbehovH += r.kundbehovMin / 60;
    k.personalbehovH += r.personalbehovMin / 60;
  }
  // Gemensamma insatser visas separat och ingår samtidigt i totalsumman.
  return [...m.values()].sort((a, c) => c.kundbehovH - a.kundbehovH);
}

// ---------- Resurskurva (30-minutersintervall) ----------

/**
 * Fördelar insatsens förväntade minuter (× dubbelbemanning) proportionellt
 * över de 30-minutersintervall som överlappar insatsens tidsfönster
 * (planerad start → fönster slut; annars planerat slut). Ett långt fönster
 * innebär inte att en medarbetare är upptagen hela intervallet.
 *
 * Returnerar per intervall: fördelade resursminuter, rått behov (min/30),
 * dimensionerat behov (uppåt till helt antal), nattgolv max(behov, 1)
 * kl. 22.00–06.00 – golvet läggs inte ovanpå ett redan högre behov.
 */
export function resurskurva(rader, fran, till) {
  const dagar = [];
  for (let d = new Date(fran + "T00:00:00Z"); d.toISOString().slice(0, 10) <= till; d.setUTCDate(d.getUTCDate() + 1)) {
    dagar.push(d.toISOString().slice(0, 10));
  }
  const idx = new Map(dagar.map((d, i) => [d, i]));
  const resursMin = new Array(dagar.length * 48).fill(0);

  for (const r of rader.map(berikaInsats)) {
    const startM = toMin(r.start);
    let slutM = r.fonsterSlut != null ? toMin(r.fonsterSlut) : toMin(r.slut);
    if (slutM == null || startM == null) continue;
    if (slutM <= startM) slutM += 1440; // fönster över midnatt
    const langd = slutM - startM;
    const s0 = Math.floor(startM / 30), s1 = Math.floor((slutM - 1) / 30);
    for (let s = s0; s <= s1; s++) {
      const lo = Math.max(startM, s * 30), hi = Math.min(slutM, (s + 1) * 30);
      const dagOffset = s >= 48 ? 1 : 0;
      const di = idx.get(r.datum) + dagOffset;
      if (di >= dagar.length) continue; // spill utanför vald period
      resursMin[di * 48 + (s % 48)] += r.personalbehovMin * ((hi - lo) / langd);
    }
  }

  const intervall = [];
  let raTotH = 0, dimensionerandeH = 0, dimensioneratMaxTotH = 0;
  let topp = { rabehov: 0, datum: null, klockan: null };
  for (let di = 0; di < dagar.length; di++) {
    for (let s = 0; s < 48; s++) {
      const min = resursMin[di * 48 + s];
      const rabehov = min / 30;
      const timme = Math.floor((s * 30) / 60);
      const natt = timme >= 22 || timme < 6;
      const medNattgolv = natt ? Math.max(rabehov, 1) : rabehov; // max(behov, 1), ej adderat
      const dimensionerat = Math.max(Math.ceil(rabehov - 1e-9), natt ? 1 : 0);
      intervall.push({
        datum: dagar[di],
        klockan: `${String(Math.floor(s / 2)).padStart(2, "0")}:${s % 2 ? "30" : "00"}`,
        resursMin: min, rabehov, medNattgolv, dimensionerat,
      });
      raTotH += rabehov * 0.5;
      dimensionerandeH += medNattgolv * 0.5;
      dimensioneratMaxTotH += dimensionerat * 0.5;
      if (rabehov > topp.rabehov) topp = { rabehov, datum: dagar[di], klockan: intervall[intervall.length - 1].klockan };
    }
  }
  return {
    intervall,
    rattResursbehovTotH: raTotH,
    dimensionerandeDirektResursbehovH: dimensionerandeH, // inkl. nattgolv
    topp: { ...topp, dimensionerat: Math.ceil(topp.rabehov - 1e-9) },
  };
}

// ---------- Bemanningsplan och ekonomi ----------

export function ekonomi({ planeradeTimmar, timkostnad, dimensionerandeH }) {
  return {
    planeradeTimmar,
    timkostnad,
    planeradKostnad: planeradeTimmar * timkostnad, // planerade timmar × timkostnad
    dimensionerandeDirektResursbehovH: dimensionerandeH,
    planeradOverkapacitetH: planeradeTimmar - dimensionerandeH,
  };
}

// ---------- Procentsatser (aldrig en enda otydlig "kundnära tid") ----------

export function procentsatser({ kundbehovH, personalbehovH, dimensionerandeH, planeradeTimmar, faktiskArbetadTidH = null, kundnaraDefinitionFinns = false, faktiskKundnaraH = null }) {
  const p = (x) => (planeradeTimmar > 0 ? (x / planeradeTimmar) * 100 : null);
  return {
    kundbehovAvPlanerade: { varde: p(kundbehovH), formel: "kundbehov ÷ planerade timmar" },
    personalbehovAvPlanerade: { varde: p(personalbehovH), formel: "personalbehov inkl. dubbelbemanning ÷ planerade timmar" },
    dimensionerandeAvPlanerade: { varde: p(dimensionerandeH), formel: "dimensionerande direkt resursbehov ÷ planerade timmar" },
    mal: { varde: 75, typ: "mål", kommentar: "Målet påverkar inte beräkningen." },
    faktiskKundnaraAndel:
      faktiskArbetadTidH != null && faktiskArbetadTidH > 0 && kundnaraDefinitionFinns && faktiskKundnaraH != null
        ? { varde: (faktiskKundnaraH / faktiskArbetadTidH) * 100, formel: "faktisk kundnära tid ÷ faktisk arbetad tid" }
        : { varde: null, text: "Kan inte beräknas" },
  };
}

// ---------- Importkontroll ----------

export function importkontroll(rader, { fran, till, forvantadeKunder = null, kontrollsummor = null } = {}) {
  const varningar = [], avvisade = [];
  const godkanda = [];
  const sett = new Map(); // dedupe på stabilt ID – återimport ersätter, skapar inte dubbletter
  for (const r of rader) {
    const fel = [];
    if (!r.datum || !/^\d{4}-\d{2}-\d{2}$/.test(r.datum)) fel.push("ogiltigt datum");
    if (toMin(r.start) == null) fel.push("saknar starttid");
    if (!(Number.isFinite(r.minuter) && r.minuter > 0)) fel.push("ogiltiga minuter");
    if (!normKund(r.kund)) fel.push("saknar kund");
    if (fel.length) { avvisade.push({ kallrad: r.kallrad, orsak: fel.join(", ") }); continue; }
    const id = r.id || stabiltId(r);
    if (sett.has(id)) { sett.set(id, { ...r, id }); varningar.push(`rad ${r.kallrad}: ersatte befintlig insats ${id}`); }
    else sett.set(id, { ...r, id });
  }
  godkanda.push(...sett.values());
  const iPeriod = filtreraPeriod(godkanda, fran, till);
  const kunder = perKund(iPeriod);
  const n = nyckeltal(iPeriod);

  let blockera = false;
  if (forvantadeKunder) {
    for (const k of forvantadeKunder) {
      const hit = kunder.find(x => x.kund === k);
      if (!hit || hit.insatser === 0) { blockera = true; varningar.push(`BLOCKERAT: kunden "${k}" saknas eller har 0 insatser`); }
    }
  }
  if (kontrollsummor) {
    const diffH = Math.abs(n.kundbehovH - kontrollsummor.kundbehovH);
    const diffI = Math.abs(n.antalInsatser - kontrollsummor.antalInsatser);
    if (diffH > 0.05 || diffI > 0) { blockera = true; varningar.push(`BLOCKERAT: totalsummor avviker (Δ ${diffI} insatser, Δ ${diffH.toFixed(2)} h)`); }
  }
  return {
    valdPeriod: { fran, till },
    lastaRader: rader.length,
    godkandaRader: godkanda.length,
    avvisadeRader: avvisade.length,
    avvisade,
    antalKunder: kunder.length,
    antalGemensamma: iPeriod.filter(r => /^gemensam/i.test(normKund(r.kund))).length,
    antalFasta: iPeriod.filter(r => !r.flyttbar).length,
    antalFlyttbara: iPeriod.filter(r => r.flyttbar).length,
    antalDubbelbemannade: n.dubbelbemannadeRader,
    timmarPerKund: kunder,
    kundbehovH: n.kundbehovH,
    personalbehovH: n.personalbehovH,
    varningar,
    blockera,
    godkanda,
  };
}

export const core = { normKund, stabiltId, filtreraPeriod, berikaInsats, nyckeltal, perKund, resurskurva, ekonomi, procentsatser, importkontroll };

