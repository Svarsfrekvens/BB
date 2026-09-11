import { describe, it, expect } from "vitest";
import { ekonomi } from "@/lib/bb/core";
import {
  DEFAULT_WORK_TIME_MODEL_ID,
  STANDARD_WORK_TIME_MODELS,
  defaultWeeklyHours,
  listPeriodDays,
  periodCapacityMinutes,
} from "@/lib/bb/arbetstid";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

function person(namn: string, extra: Partial<Medarbetare> = {}): Medarbetare {
  return {
    namn,
    vakant: false,
    vikarie: false,
    grad: 100,
    samordnare: false,
    delegering: true,
    jour: true,
    nattbehorig: true,
    passprofil: extra.passprofil ?? "blandat",
    helg: "varannan",
    tidigastStart: "",
    senastSlut: "",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
    ...extra,
  };
}

const rad: Insats = {
  id: "1",
  datum: "2026-09-07",
  kund: "Kund A",
  insats: "Stöd",
  start: "09:00",
  minuter: 60,
} as Insats;

describe("arbetstidsmodell i payload och visning", () => {
  it("sätter katalog och verksamhetsdefault, inte personal[0] som allas mått", () => {
    const r = byggMotorPayload({
      rader: [rad],
      medarbetare: [person("Alfa"), person("Beta")],
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
      heltidPerNamn: { Alfa: 40 },
    });
    const wp = r.payload.workplace as {
      workTimeModels: { id: string; weeklyMinutes: number }[];
      defaultWorkTimeModelId: string;
    };
    expect(wp.defaultWorkTimeModelId).toBe(DEFAULT_WORK_TIME_MODEL_ID);
    expect(wp.workTimeModels.map((m) => m.id)).toEqual(expect.arrayContaining(STANDARD_WORK_TIME_MODELS.map((m) => m.id)));
    const emps = r.payload.employees as { name: string; workTimeModelId?: string }[];
    const ordinarie = emps.filter((e) => !String(e.name).startsWith("Extra"));
    const alfa = ordinarie.find((e) => e.name === "Alfa");
    const beta = ordinarie.find((e) => e.name === "Beta");
    expect(alfa?.workTimeModelId).toBe("helgfri-40");
    expect(beta?.workTimeModelId).toBeUndefined();
    expect((r.payload.rules as { maxWeeklyHours: number }).maxWeeklyHours).toBe(48);
    expect((r.payload.rules as { fullTimeWeeklyHours: number }).fullTimeWeeklyHours).toBe(defaultWeeklyHours());
  });

  it("passprofil byter inte arbetstidsmått", () => {
    const r = byggMotorPayload({
      rader: [rad],
      medarbetare: [person("Natt", { passprofil: "natt" }), person("Dag", { passprofil: "dag" })],
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
    });
    const emps = (r.payload.employees as { name: string; workTimeModelId?: string }[]).filter(
      (e) => e.name === "Natt" || e.name === "Dag",
    );
    expect(emps.every((e) => !e.workTimeModelId)).toBe(true);
  });

  it("ekonomi är oförändrad när schematiden är densamma", () => {
    const a = ekonomi({ planeradeTimmar: 120, timkostnad: 270, dimensionerandeH: 100 });
    const b = ekonomi({ planeradeTimmar: 120, timkostnad: 270, dimensionerandeH: 100 });
    expect(a.planeradKostnad).toBe(120 * 270);
    expect(a.planeradKostnad).toBe(b.planeradKostnad);
  });

  it("periodkapacitet är days/7 och oberoende av 4,345", () => {
    const days = listPeriodDays("2026-09-07", "2026-09-16");
    expect(days.length).toBe(10);
    const cap = periodCapacityMinutes(
      { ssg: 100, workTimeModelId: "vardag-helg-37" },
      days,
      { fullTimeWeeklyHours: 40 },
      { workTimeModels: STANDARD_WORK_TIME_MODELS, defaultWorkTimeModelId: DEFAULT_WORK_TIME_MODEL_ID },
    );
    expect(cap / 60).toBeCloseTo(37 * (10 / 7), 5);
  });
});
