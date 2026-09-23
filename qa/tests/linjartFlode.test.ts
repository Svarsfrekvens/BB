import { describe, it, expect } from "vitest";
import { nastaFlodesTab, hemAteruppta, flodesTabAlias } from "@/lib/bb/linjartFlode";
import { OVERSIKT_PROCESS } from "@/lib/bb/oversiktProcess";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const tom = {
  harKundrader: false,
  kundGodkand: false,
  harSchema: false,
  schemaGodkand: false,
  harBalans: false,
  balansGodkand: false,
};

describe("Linjärt arbetsflöde", () => {
  it("går Kundbehov → schemauppladdning efter godkänt kundunderlag", () => {
    expect(nastaFlodesTab({ ...tom, harKundrader: true, kundGodkand: true })).toBe("uppladdning");
  });

  it("går till Medarbetare när schema är inläst men inte godkänt", () => {
    expect(
      nastaFlodesTab({
        ...tom,
        harKundrader: true,
        kundGodkand: true,
        harSchema: true,
      }),
    ).toBe("medarbetare");
  });

  it("går till Planering efter godkänt medarbetare & villkor", () => {
    expect(
      nastaFlodesTab({
        ...tom,
        harKundrader: true,
        kundGodkand: true,
        harSchema: true,
        schemaGodkand: true,
      }),
    ).toBe("planering");
  });

  it("Hem återupptar nästa steg och skickar inte tillbaka till Hem", () => {
    const a = hemAteruppta({
      ...tom,
      harKundrader: true,
      kundGodkand: true,
      harSchema: true,
      schemaGodkand: true,
    });
    expect(a.tab).not.toBe("hem");
    expect(a.tab).toBe("planering");
  });

  it("kopplar Planering till planeringsvyn, inte resultat", () => {
    expect(OVERSIKT_PROCESS.find((s) => s.id === "planering")?.tab).toBe("planering");
    expect(OVERSIKT_PROCESS.find((s) => s.id === "granska")?.tab).toBe("forutsattningar");
    expect(OVERSIKT_PROCESS.find((s) => s.id === "balans")?.tab).toBe("foreefter");
    expect(flodesTabAlias("resultat")).toBe("foreefter");
  });

  it("Kundbehov har inget andra godkännande av samma underlag", () => {
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../src/components/bb/Kundbehov.tsx"), "utf8");
    expect(src).not.toContain("Godkänn kundunderlaget");
    expect(src).toContain("Godkänn ändringar");
  });
});
