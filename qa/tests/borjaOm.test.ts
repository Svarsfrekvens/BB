import { describe, expect, it } from "vitest";
import {
  BORJA_OM_STARTLAGE,
  BORJA_OM_TAB,
  harKvarvarandeArbete,
  nollstalltArbetsminne,
} from "@/lib/bb/borjaOm";
import { hamtaStartlage } from "@/lib/bb/startlage";

describe("Börja om ger tom Startsida", () => {
  const galaxen = {
    rows: [{ id: 1 }],
    period: { from: "2026-08-03", to: "2026-08-30" },
    schemaOriginal: { medarbetare: [{ namn: "A" }], pass: [{ id: "p1" }] },
    balans: { schematidH: 832 },
    motorResultat: { schedule: { shifts: [1] } },
    motorJobb: { id: "98fa19df", phase: "completed" },
    extraResurser: [{ id: "t1" }],
    optimerat: true,
    balansGodkand: true,
    kundGodkand: true,
    schemaGodkand: true,
    jamfor: { fore: 832 },
    nyttSchema: { pass: [1] },
    kundEdit: { rows: [1] },
    schemaLek: { moves: {} },
  };

  it("nollställer Balans, motorresultat, jobb och underlag", () => {
    expect(harKvarvarandeArbete(galaxen)).toBe(true);
    const efter = nollstalltArbetsminne();
    expect(efter.balans).toBeNull();
    expect(efter.motorResultat).toBeNull();
    expect(efter.motorJobb).toBeNull();
    expect(efter.schemaOriginal).toBeNull();
    expect(efter.rows).toEqual([]);
    expect(efter.extraResurser).toEqual([]);
    expect(efter.optimerat).toBe(false);
    expect(efter.balansGodkand).toBe(false);
    expect(efter.jamfor).toBeNull();
    expect(harKvarvarandeArbete(efter)).toBe(false);
  });

  it("pekar Startsida, inte Underlag eller Före → Balans", () => {
    expect(BORJA_OM_STARTLAGE).toBe("start");
    expect(BORJA_OM_TAB).toBe("hem");
    expect(BORJA_OM_STARTLAGE).not.toBe("app");
    expect(["start", "upload", "app"]).toContain(hamtaStartlage());
  });
});
