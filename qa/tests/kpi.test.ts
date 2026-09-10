import { describe, it, expect } from "vitest";
import { beraknaKpi } from "@/lib/bb/kpi";
import { expanderaAktiviteter, standardKatalog, kunderUtanKontakt } from "@/lib/bb/aktiviteter";
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

  it("scenario B: 340 / 400 = 85 %", () => {
    const k = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 300 + 20 + 20,
      totaltKundbehovH: 300,
      bemannatKundbehovH: 300,
    });
    expect(k.kundnaraH).toBe(340);
    expect(k.ejKundnaraH).toBe(60);
    expect(k.kundnaraPct).toBeCloseTo(85, 5);
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

  it("kapas inte till 100 % – felaktig täljare syns", () => {
    const k = beraknaKpi({
      schematidH: 400,
      kundnaraArbetstidH: 500,
      totaltKundbehovH: 100,
      bemannatKundbehovH: 100,
    });
    expect(k.kundnaraPct).toBeCloseTo(125, 5);
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

  it("kontaktpersonsaktiviteter kräver koppling", () => {
    const katalog = standardKatalog().map((a) => (a.id === "veckoavstamning" ? { ...a, aktiv: true } : a));
    expect(kunderUtanKontakt(["A", "B"], { A: "Med 1" }, katalog)).toEqual(["B"]);
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
