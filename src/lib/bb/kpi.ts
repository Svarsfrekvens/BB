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
