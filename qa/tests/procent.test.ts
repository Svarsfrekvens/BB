import { describe, it, expect } from "vitest";
import { procentsatser } from "@/lib/bb/core";

describe("procentsatser", () => {
  it("planeradeTimmar 0 ger null, aldrig NaN eller Infinity", () => {
    const p = procentsatser({
      kundbehovH: 578.8,
      personalbehovH: 600,
      dimensionerandeH: 793.8,
      planeradeTimmar: 0,
    });
    const varden = [
      p.kundbehovAvPlanerade.varde,
      p.personalbehovAvPlanerade.varde,
      p.dimensionerandeAvPlanerade.varde,
    ];
    for (const v of varden) {
      expect(v).toBeNull();
      expect(Number.isNaN(v as number)).toBe(false);
      expect(v).not.toBe(Infinity);
      expect(v).not.toBe(-Infinity);
    }
  });
});
