/** Gemensam KPI-definition för Före, Efter, Översikt och tester.
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
};

export function beraknaKpi(d: KpiIndata): KpiResultat {
  const schematidH = Math.max(0, d.schematidH);
  const kundnaraH = Math.max(0, d.kundnaraArbetstidH);
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
  };
}
