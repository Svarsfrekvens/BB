import { describe, it, expect } from "vitest";
import { stockholmKlocka, tolkaMotorSchema } from "@/lib/bb/motorResultat";

describe("tolkaMotorSchema – sommartid", () => {
  it("UTC-minuter över omställningen 2026-10-25 ger rätt lokal tid", () => {
    // 25 okt 2026: klockan ställs tillbaka 03:00 CEST → 02:00 CET.
    const startUtc = Date.parse("2026-10-25T00:30:00.000Z") / 60000; // 02:30 sommartid
    const slutUtc = Date.parse("2026-10-25T07:00:00.000Z") / 60000; // 08:00 vintertid
    expect(stockholmKlocka(startUtc)).toBe("02:30");
    expect(stockholmKlocka(slutUtc)).toBe("08:00");

    const schema = tolkaMotorSchema(
      JSON.stringify({
        solverStatus: "OPTIMAL",
        explanation: "test",
        shifts: [],
        assignments: [
          {
            occurrenceId: "i1@2026-10-25",
            employeeId: "e1",
            start: startUtc,
            end: slutUtc,
          },
        ],
        uncovered: [],
        objective: 0,
        bound: 0,
      }),
      {
        medarbetare: { e1: { namn: "Anna", vikarie: false } },
        insatser: { i1: { radId: "1", kund: "Kund", insats: "Stöd", start: "02:00" } },
      },
    );
    expect(schema).toBeTruthy();
    expect(schema!.tilldelningar[0]?.start).toBe("02:30");
    expect(schema!.tilldelningar[0]?.slut).toBe("08:00");
    expect(schema!.tilldelningar[0]?.datum).toBe("2026-10-25");
  });

  it("läser objectiveBreakdown ur motorns svar", () => {
    const schema = tolkaMotorSchema(
      JSON.stringify({
        solverStatus: "OPTIMAL",
        assignments: [],
        uncovered: [],
        objectiveBreakdown: { costOre: 1000, continuityOre: 5000, spreadOre: 250 },
      }),
      { medarbetare: {}, insatser: {} },
    );
    expect(schema?.objectiveBreakdown).toEqual({ costOre: 1000, continuityOre: 5000, spreadOre: 250 });
  });

  it("märker type jour som sovande jour", () => {
    const schema = tolkaMotorSchema(
      JSON.stringify({
        solverStatus: "OPTIMAL",
        shifts: [
          {
            id: "j1",
            employeeId: "e1",
            date: "2026-08-03",
            start: "23:00",
            end: "06:30",
            type: "jour",
            breaks: [],
          },
        ],
        assignments: [],
        uncovered: [],
      }),
      { medarbetare: { e1: { namn: "Anna", vikarie: false } }, insatser: {} },
    );
    expect(schema?.pass[0]?.jour).toBe(true);
    expect(schema?.pass[0]?.timmar).toBe(7.5);
  });

  it("läser schedule.uncovered till insats, datum och minuter", () => {
    const schema = tolkaMotorSchema(
      JSON.stringify({
        solverStatus: "OPTIMAL",
        assignments: [],
        uncovered: [{ occurrenceId: "i1@2026-08-03", name: "Tillsyn", date: "2026-08-03", minutes: 30, count: 1 }],
      }),
      { medarbetare: {}, insatser: {} },
    );
    expect(schema?.obemannade).toEqual([{ insats: "Tillsyn", datum: "2026-08-03", minuter: 30, antal: 1 }]);
  });
});
