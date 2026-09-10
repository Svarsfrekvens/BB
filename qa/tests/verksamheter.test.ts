import { describe, it, expect } from "vitest";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { standardKatalog } from "@/lib/bb/aktiviteter";
import type { Medarbetare } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";

function personal(n: number, extra: Partial<Medarbetare> = {}): Medarbetare[] {
  return Array.from({ length: n }, (_, i) => ({
    namn: `P${i + 1}`,
    vakant: false,
    vikarie: false,
    grad: 100,
    samordnare: false,
    delegering: true,
    jour: extra.jour ?? true,
    nattbehorig: extra.nattbehorig ?? true,
    passprofil: extra.passprofil ?? "blandat",
    helg: extra.helg ?? "varannan",
    tidigastStart: "06:30",
    senastSlut: "23:00",
    maxDagarIFoljd: 5,
    franvaro: "ingen",
    timkostnad: 270,
    anstallning: "manad",
    villkor: extra.villkor,
  }));
}

function rader(nKunder: number): Insats[] {
  return Array.from({ length: nKunder }, (_, i) => ({
    id: `r${i}`,
    datum: "2026-09-07",
    kund: `Kund ${i + 1}`,
    insats: "Stöd",
    start: "09:00",
    slut: "10:00",
    minuter: 60,
    tvaPersoner: false,
    flyttbar: false,
    status: "Utförd",
    kallrad: i,
  })) as Insats[];
}

describe("samma motor för tre verksamhetsprofiler", () => {
  it("A jour, B utan jour, C annan helg och aktiviteter – ingen verksamhetsspecifik gren", () => {
    const a = byggMotorPayload({
      rader: rader(6),
      medarbetare: personal(11, { jour: true }),
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
    });
    const b = byggMotorPayload({
      rader: rader(3),
      medarbetare: personal(4, { jour: false, nattbehorig: false }),
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
      mallar: [{ id: "dag", type: "day", start: "07:00", end: "16:00", breaks: [], skills: [] }],
    });
    const katalog = standardKatalog().map((x) => (x.id === "veckoavstamning" ? { ...x, aktiv: true } : x));
    const c = byggMotorPayload({
      rader: rader(2),
      medarbetare: personal(3, { helg: "vartredje" }),
      from: "2026-09-07",
      dagar: 28,
      timkostnad: 270,
      planAktiviteter: katalog,
      kontaktpersoner: { "Kund 1": "P1", "Kund 2": "P1" },
    });
    expect(a.payload.schemaVersion).toBe(1);
    expect(b.payload.schemaVersion).toBe(1);
    expect(c.payload.schemaVersion).toBe(1);
    const insC = (c.payload.interventions as { name: string; requiredEmployeeId?: string }[]) || [];
    expect(insC.some((i) => i.name === "Veckoavstämning kund" && i.requiredEmployeeId === "e1")).toBe(true);
  });

  it("datumstyrd SSG och kundförbud går in i samma payload utan verksamhetsgren", () => {
    const p = byggMotorPayload({
      rader: rader(2),
      medarbetare: personal(2, {
        villkor: [
          { id: "s", typ: "ssg", styrka: "maste", from: "2026-09-07", till: "2026-09-10", aktiv: true, payload: { ssg: 50 } },
          { id: "k", typ: "kundforbud", styrka: "maste", from: "2026-09-07", till: "2026-09-13", aktiv: true, payload: { kund: "Kund 2" } },
        ],
      }),
      from: "2026-09-07",
      dagar: 7,
      timkostnad: 270,
    });
    const emp = (p.payload.employees as { ssgWindows: { ssg: number }[]; skills: string[] }[])[0]!;
    expect(emp.ssgWindows[0]?.ssg).toBe(50);
    expect(emp.skills.some((s) => s === "kund:k2")).toBe(false);
    expect(emp.skills.some((s) => s === "kund:k1")).toBe(true);
  });
});
