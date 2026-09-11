/** Gemensam KPI-definition för Före, Efter, Översikt, Uppföljning och tester.
 * Kundnära tid = schemalagd kundnära arbetstid ÷ total schemalagd arbetstid.
 * Täckt behov = bemannat kundbehov ÷ totalt kundbehov.
 * Obemannat kundbehov får aldrig ingå i kundnära täljare. */

export type KpiIndata = {
  /** Arbetspasstid exkl. sovande jour och raster. */
  schematidH: number;
  /** Tid som faktiskt ligger på schemalagd personal och klassas som kundnära. */
  kundnaraArbetstidH: number;
  totaltKundbehovH: number;
  bemannatKundbehovH: number;
};

export type KpiResultat = {
  schematidH: number;
  kundnaraH: number;
  ejKundnaraH: number;
  kundnaraPct: number;
  totaltKundbehovH: number;
  bemannatKundbehovH: number;
  obemannatKundbehovH: number;
  tacktBehovPct: number;
  /** Sant när indata bröt invarianten – KPI:n hålls inom 0…schematid, inte kosmetiskt i UI. */
  modellFel: boolean;
};

/** Rymmer inom-pass-aktiviteter i kvarvarande passkapacitet. Skapar ingen osynlig tid. */
export function rymInomPass(d: {
  schematidH: number;
  direktKundnaraH: number;
  inomPassKundnaraH: number;
  inomPassEjKundnaraH?: number;
}) {
  const schematidH = Math.max(0, d.schematidH);
  const direkt = Math.max(0, d.direktKundnaraH);
  const extraK = Math.max(0, d.inomPassKundnaraH);
  const extraE = Math.max(0, d.inomPassEjKundnaraH || 0);
  const kvar = Math.max(0, schematidH - direkt);
  const rymdKundnaraH = Math.min(extraK, kvar);
  const kvarEfter = Math.max(0, kvar - rymdKundnaraH);
  const rymdEjKundnaraH = Math.min(extraE, kvarEfter);
  const overflowH = extraK - rymdKundnaraH + (extraE - rymdEjKundnaraH) + Math.max(0, direkt - schematidH);
  return {
    schematidH,
    direktKundnaraH: Math.min(direkt, schematidH),
    rymdKundnaraH,
    rymdEjKundnaraH,
    overflowH,
    platsBrist: overflowH > 1e-9,
    kundnaraH: Math.min(schematidH, Math.min(direkt, schematidH) + rymdKundnaraH),
  };
}

/** Rymmer inom-pass-aktiviteter i varje faktiskt arbetspass. Per-pass-tid
 *  fördelas jämnt; övrig inom-pass-tid packas i ledig kapacitet per pass. */
export function rymIArbetspass(d: {
  pass: { timmar: number; direktKundnaraH: number }[];
  perPassKundnaraH?: number;
  perPassEjKundnaraH?: number;
  periodKundnaraH?: number;
  periodEjKundnaraH?: number;
}) {
  const n = d.pass.length;
  const perK = n ? Math.max(0, d.perPassKundnaraH || 0) / n : Math.max(0, d.perPassKundnaraH || 0);
  const perE = n ? Math.max(0, d.perPassEjKundnaraH || 0) / n : Math.max(0, d.perPassEjKundnaraH || 0);
  let overflowH = 0;
  let kundnaraH = 0;
  let schematidH = 0;
  const leftover: number[] = [];
  if (!n) {
    overflowH = Math.max(0, d.perPassKundnaraH || 0) + Math.max(0, d.perPassEjKundnaraH || 0)
      + Math.max(0, d.periodKundnaraH || 0) + Math.max(0, d.periodEjKundnaraH || 0);
    return { schematidH: 0, kundnaraH: 0, overflowH, platsBrist: overflowH > 1e-9 };
  }
  for (const p of d.pass) {
    const h = Math.max(0, p.timmar);
    schematidH += h;
    const direkt = Math.min(Math.max(0, p.direktKundnaraH), h);
    let kvar = Math.max(0, h - direkt);
    const k1 = Math.min(perK, kvar);
    kvar -= k1;
    const e1 = Math.min(perE, kvar);
    kvar -= e1;
    overflowH += perK - k1 + (perE - e1);
    kundnaraH += direkt + k1;
    leftover.push(kvar);
  }
  let pk = Math.max(0, d.periodKundnaraH || 0);
  let pe = Math.max(0, d.periodEjKundnaraH || 0);
  for (let i = 0; i < leftover.length; i++) {
    const take = Math.min(pk, leftover[i] || 0);
    leftover[i] = (leftover[i] || 0) - take;
    pk -= take;
    kundnaraH += take;
  }
  for (let i = 0; i < leftover.length; i++) {
    const take = Math.min(pe, leftover[i] || 0);
    leftover[i] = (leftover[i] || 0) - take;
    pe -= take;
  }
  overflowH += pk + pe;
  return {
    schematidH,
    kundnaraH: Math.min(schematidH, kundnaraH),
    overflowH,
    platsBrist: overflowH > 1e-9,
  };
}

export function beraknaKpi(d: KpiIndata): KpiResultat {
  const schematidH = Math.max(0, d.schematidH);
  const rawKundnara = Math.max(0, d.kundnaraArbetstidH);
  const modellFel = rawKundnara > schematidH + 1e-9;
  const kundnaraH = Math.min(rawKundnara, schematidH);
  const totalt = Math.max(0, d.totaltKundbehovH);
  const bemannat = Math.max(0, Math.min(d.bemannatKundbehovH, totalt));
  return {
    schematidH,
    kundnaraH,
    ejKundnaraH: Math.max(0, schematidH - kundnaraH),
    kundnaraPct: schematidH > 0 ? (kundnaraH / schematidH) * 100 : 0,
    totaltKundbehovH: totalt,
    bemannatKundbehovH: bemannat,
    obemannatKundbehovH: Math.max(0, totalt - bemannat),
    tacktBehovPct: totalt > 0 ? (bemannat / totalt) * 100 : 100,
    modellFel,
  };
}
