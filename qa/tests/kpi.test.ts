import { describe, it, expect } from "vitest";
import { beraknaKpi } from "@/lib/bb/kpi";
import { expanderaAktiviteter, standardKatalog, kunderUtanKontakt, aktivitetstimmar } from "@/lib/bb/aktiviteter";
import { ssgForDag, gallerIPeriod, type MedarbetarVillkor } from "@/lib/bb/villkor";

describe("KPI kundnära tid och täckt behov", () => {
  it("scenario A: 350 / 400 = 87,5 %, inte 100 % trots 600 h behov", () => {
    const k = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 350,
      totaltKundbehovH: 600,
      bemannatKundbehovH: 350,
    });
    expect(k.kundnaraPct).toBeCloseTo(87.5, 5);
    expect(k.kundnaraPct).toBeLessThan(100);
    expect(k.tacktBehovPct).toBeCloseTo((350 / 600) * 100, 5);
  });

  it("scenario B: 8 h pass, 6 h insats, 30 min journal inom pass → 81,25 %, inte 8,5 h", () => {
    const k = beraknaKpi({
      schematidH: 8,
      kundnaraArbetstidH: 6 + 0.25 + 0.25,
      totaltKundbehovH: 6,
      bemannatKundbehovH: 6,
    });
    expect(k.schematidH).toBe(8);
    expect(k.kundnaraH).toBeCloseTo(6.5, 5);
    expect(k.ejKundnaraH).toBeCloseTo(1.5, 5);
    expect(k.kundnaraPct).toBeCloseTo(81.25, 5);
    expect(k.modellFel).toBe(false);
  });

  it("scenario C: obemannat behov höjer inte kundnära tid", () => {
    const utan = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 300,
      totaltKundbehovH: 300,
      bemannatKundbehovH: 300,
    });
    const medObemannat = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 300,
      totaltKundbehovH: 500,
      bemannatKundbehovH: 300,
    });
    expect(medObemannat.kundnaraH).toBe(utan.kundnaraH);
    expect(medObemannat.kundnaraPct).toBe(utan.kundnaraPct);
    expect(medObemannat.tacktBehovPct).toBeLessThan(utan.tacktBehovPct);
    expect(medObemannat.obemannatKundbehovH).toBe(200);
  });

  it("överskriden täljare är modellfel och KPI håller invariant", () => {
    const k = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 500,
      totaltKundbehovH: 100,
      bemannatKundbehovH: 100,
    });
    expect(k.modellFel).toBe(true);
    expect(k.kundnaraH).toBe(400);
    expect(k.kundnaraPct).toBeCloseTo(100, 5);
    expect(k.ejKundnaraH).toBe(0);
  });
});

describe("planeringsaktiviteter", () => {
  it("sparad katalog återanvänds och inaktiv påverkar inte timmar", () => {
    const katalog = standardKatalog();
    katalog.find((a) => a.id === "lasa_journal")!.aktiv = true;
    katalog.find((a) => a.id === "lasa_journal")!.omfattning = 10;
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-28",
      arbetspass: 40,
      kunder: ["A"],
      kontaktpersoner: {},
    });
    expect(exp.find((e) => e.typ === "lasa_journal")?.timmar).toBeCloseTo(40 * 10 / 60, 5);
    expect(exp.find((e) => e.typ === "verksamhetsmote")).toBeUndefined();
  });

  it("ej kundnära ligger inte i kundnära timmar", () => {
    const katalog = standardKatalog().map((a) =>
      a.id === "verksamhetsmote" || a.id === "lasa_journal" ? { ...a, aktiv: true } : a,
    );
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-30",
      arbetspass: 10,
      kunder: [],
      kontaktpersoner: {},
    });
    expect(exp.find((e) => e.typ === "verksamhetsmote")?.kundnara).toBe(false);
    expect(exp.find((e) => e.typ === "lasa_journal")?.kundnara).toBe(true);
  });

  it("dubbelräknar inte om Sekoia redan har samma aktivitet", () => {
    const katalog = standardKatalog().map((a) => (a.id === "gp" ? { ...a, aktiv: true } : a));
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-30",
      arbetspass: 0,
      kunder: ["Kund A"],
      kontaktpersoner: {},
      sekoiaRader: [{ insats: "Genomförandeplan uppföljning", kund: "Kund A" }],
    });
    expect(exp.filter((e) => e.typ === "gp")).toHaveLength(0);
  });

  it("ändrad schablon används", () => {
    const katalog = standardKatalog().map((a) =>
      a.id === "lasa_journal" ? { ...a, aktiv: true, omfattning: 20 } : a,
    );
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-07",
      arbetspass: 10,
      kunder: [],
      kontaktpersoner: {},
    });
    expect(exp.find((e) => e.typ === "lasa_journal")?.timmar).toBeCloseTo(10 * 20 / 60, 5);
  });

  it("inom_pass räknas separat från separat_tid", () => {
    const katalog = standardKatalog().map((a) =>
      a.id === "lasa_journal" || a.id === "verksamhetsmote" ? { ...a, aktiv: true } : a,
    );
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-30",
      arbetspass: 10,
      kunder: [],
      kontaktpersoner: {},
    });
    const tim = aktivitetstimmar(exp);
    expect(tim.inomPassKundnaraH).toBeCloseTo(10 * 10 / 60, 5);
    expect(tim.separatEjKundnaraH).toBeGreaterThan(0);
    expect(exp.find((e) => e.typ === "lasa_journal")?.tidstyp).toBe("inom_pass");
    expect(exp.find((e) => e.typ === "verksamhetsmote")?.tidstyp).toBe("separat_tid");
  });

  it("kontaktpersonstid knyts till medarbetare 1", () => {
    const katalog = standardKatalog().map((a) =>
      a.id === "kontaktpersonstid" || a.id === "veckoavstamning" || a.id === "manadsuppfoljning"
        ? { ...a, aktiv: true }
        : a,
    );
    const exp = expanderaAktiviteter({
      aktiviteter: katalog,
      fran: "2026-09-01",
      till: "2026-09-28",
      arbetspass: 0,
      kunder: ["Kund A"],
      kontaktpersoner: { "Kund A": "Medarbetare 1" },
    });
    expect(exp.filter((e) => e.medarbetare === "Medarbetare 1").length).toBeGreaterThanOrEqual(3);
  });
});

describe("datumstyrd SSG", () => {
  const villkor: MedarbetarVillkor[] = [
    { id: "1", typ: "ssg", styrka: "maste", from: "2026-09-15", till: "2026-09-30", aktiv: true, payload: { ssg: 75 } },
  ];
  it("100 % före 15:e och 75 % därefter", () => {
    expect(ssgForDag(100, villkor, "2026-09-01")).toBe(100);
    expect(ssgForDag(100, villkor, "2026-09-15")).toBe(75);
    expect(ssgForDag(100, villkor, "2026-09-30")).toBe(75);
  });
  it("utgånget villkor påverkar inte ny period", () => {
    expect(gallerIPeriod(villkor[0]!, "2026-10-01", "2026-10-28")).toBe(false);
  });
});
