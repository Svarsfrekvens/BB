import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  FORHANDSANALYS_RUBRIK,
  FORHANDSANALYS_TEXT,
  arFardigMotorBalans,
  berakningsKallaText,
  godkannBeslutFranVy,
  visningsFas,
} from "@/lib/bb/vcFlode";

const rot = join(__dirname, "../..");

const motorResultat = (s: Record<string, unknown> = {}) => ({
  summary: { status: "FEASIBLE", cost: 1, warnings: [], hardViolations: [], coveragePercent: 100, ...s },
});

describe("Förhandsanalys är inte färdig Balans", () => {
  it("utan motorresultat blir rubrik/fas Förhandsanalys, inte färdig Balans", () => {
    const fas = visningsFas({ harLokalBerakning: true });
    expect(fas.id).toBe("forhandsanalys");
    expect(fas.rubrik).toBe(FORHANDSANALYS_RUBRIK);
    expect(fas.rubrik).not.toBe("Balans");
    expect(fas.text).toBe(FORHANDSANALYS_TEXT);
    expect(arFardigMotorBalans({})).toBe(false);
    expect(berakningsKallaText("lokal")).toBe("Förhandsanalys");
  });

  it("Godkänn balans är blockerad utan motorresultat även vid 100 % och 0 lokala brott", () => {
    const r = godkannBeslutFranVy({ tacktBehovPct: 100, hardViolations: 0 });
    expect(r.ok).toBe(false);
    expect(r.kalla).toBe("lokal");
    expect(r.reasons.join(" ")).toMatch(/motorn/);
  });

  it("aktuellt balans_klar visas som riktig Balans", () => {
    const d = {
      motorJobb: { outcome: "balans_klar", stale: false },
      motorResultat: motorResultat(),
      harLokalBerakning: true,
    };
    expect(arFardigMotorBalans(d)).toBe(true);
    const fas = visningsFas(d);
    expect(fas.id).toBe("balans");
    expect(fas.rubrik).toBe("Balans");
    const g = godkannBeslutFranVy({
      motorJobb: d.motorJobb,
      motorResultat: d.motorResultat,
      tacktBehovPct: 81,
      hardViolations: 89,
    });
    expect(g.ok).toBe(true);
    expect(g.kalla).toBe("motor");
  });

  it("stale motorresultat behandlas inte som färdig Balans", () => {
    const d = {
      motorJobb: { outcome: "balans_klar", stale: true },
      motorResultat: motorResultat(),
      harLokalBerakning: true,
    };
    expect(arFardigMotorBalans(d)).toBe(false);
    expect(visningsFas(d).id).toBe("forhandsanalys");
    const g = godkannBeslutFranVy({
      motorJobb: d.motorJobb,
      motorResultat: d.motorResultat,
      tacktBehovPct: 100,
      hardViolations: 0,
    });
    expect(g.ok).toBe(false);
  });

  it("tar bort den gamla missvisande produkttexten", () => {
    const modell = readFileSync(join(rot, "src/lib/bb/modell.ts"), "utf8");
    expect(modell).not.toContain(
      "Appen föreslår justeringar och räknar om siffrorna – den lägger inte ett färdigt lagligt schema automatiskt.",
    );
  });
});
