/**
 * Datum ur Excel ska läsas som visad text (D/M/Y), aldrig som SheetJS .v
 * med omkastad månad. Buggen "8:e i varje månad" = 3/8/26 blir 8 mars i stället för 3 augusti.
 */
import { describe, it, expect } from "vitest";
import { parseDatum, cellToClock } from "@/lib/bb/sekoia";

describe("parseDatum / cellToClock", () => {
  it("tolkar 3/8/26 6:30 som 3 augusti 2026, inte 8 mars", () => {
    const d = parseDatum("3/8/26 6:30");
    expect(d).toMatch(/^2026-08-/);
    expect(d).toBe("2026-08-03");
    expect(d).not.toBe("2026-03-08");
    expect(cellToClock("3/8/26 6:30")).toBe("06:30");
  });

  it("tolkar 13-08-2026 som augusti, inte den 8:e i varje månad", () => {
    expect(parseDatum("13-08-2026")).toBe("2026-08-13");
    expect(parseDatum("13-08-2026")).toMatch(/^2026-08-/);
  });

  it("tolkar ISO 2026-08-13 oförändrat", () => {
    expect(parseDatum("2026-08-13")).toBe("2026-08-13");
  });

  it("tolkar Excel-serienummer till 2026-08-xx", () => {
    // 46089,2708… är 2026-08-03 06:30 i Excel (samma tal som i Galaxen).
    const serial = 46089.270833333336;
    expect(parseDatum(serial)).toMatch(/^2026-08-/);
    expect(parseDatum(serial)).toBe("2026-08-03");
    expect(cellToClock(serial)).toBe("06:30");
  });
});
