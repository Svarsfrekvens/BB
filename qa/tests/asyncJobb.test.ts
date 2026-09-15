import { describe, expect, it } from "vitest";
import { underlagFingeravtryckFranPayload } from "@/lib/bb/korBemanningsbalans";
import { balansUtfallText, fasSteg } from "@/lib/bb/motorJobb";
import { hemStatusText } from "@/lib/bb/vcFlode";

describe("asynk balans-jobb (klient)", () => {
  it("samma underlag ger samma hash, ändrad SSG ger ny", () => {
    const a = underlagFingeravtryckFranPayload({
      workplace: { start: "2026-08-03", end: "2026-08-16" },
      employees: [{ id: "e1", ssg: 100 }],
      interventions: [1, 2, 3],
      rules: { jourFloor: 1 },
    });
    const b = underlagFingeravtryckFranPayload({
      workplace: { start: "2026-08-03", end: "2026-08-16" },
      employees: [{ id: "e1", ssg: 100 }],
      interventions: [1, 2, 3],
      rules: { jourFloor: 1 },
    });
    const c = underlagFingeravtryckFranPayload({
      workplace: { start: "2026-08-03", end: "2026-08-16" },
      employees: [{ id: "e1", ssg: 80 }],
      interventions: [1, 2, 3],
      rules: { jourFloor: 1 },
    });
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });

  it("skiljer de fyra resultatstatusarna", () => {
    expect(balansUtfallText("balans_klar")).toBe("Balans klar");
    expect(balansUtfallText("basta_hittade")).toBe("Bästa hittade Balans");
    expect(balansUtfallText("kompletteras")).toBe("Balans behöver kompletteras");
    expect(balansUtfallText("tekniskt_fel")).toBe("Kunde inte skapa Balans");
  });

  it("visar faser utan procent", () => {
    const s = fasSteg("solving");
    expect(s.find((x) => x.id === "solving")?.pa).toBe(true);
    expect(s.find((x) => x.id === "preparing")?.klar).toBe(true);
    expect(hemStatusText({
      lage: "fore",
      ready: true,
      blockingReasons: [],
      godkannbar: false,
      pagaende: true,
    })).toBe("Balans skapas");
    expect(hemStatusText({
      lage: "balans",
      ready: true,
      blockingReasons: [],
      godkannbar: false,
      klarForGranskning: true,
    })).toBe("Balans klar för granskning");
  });
});
