import { describe, expect, it } from "vitest";
import { asyncSekunderForFonster, underlagFingeravtryckFranPayload, underlagHashVidStart } from "@/lib/bb/korBemanningsbalans";
import { balansUtfallText, fasSteg, hanteraHamtaJobbSvar, AVBRUTEN_JOBB_TEXT } from "@/lib/bb/motorJobb";
import { hemStatusText, vcTextArRen } from "@/lib/bb/vcFlode";

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

  it("28d async använder 240 s per försök, kortare period 180 s", () => {
    expect(asyncSekunderForFonster(28)).toBe(240);
    expect(asyncSekunderForFonster(14)).toBe(180);
    expect(asyncSekunderForFonster(7)).toBe(180);
  });

  it("visar faser utan procent, seed eller CP-SAT", () => {
    const s = fasSteg("solving");
    expect(s.find((x) => x.id === "solving")?.pa).toBe(true);
    expect(s.find((x) => x.id === "solving")?.label).toBe("Skapar balans");
    expect(s.find((x) => x.id === "preparing")?.klar).toBe(true);
    expect(s.find((x) => x.id === "preparing")?.label).toBe("Förbereder underlag");
    expect(s.find((x) => x.id === "validating")?.label).toBe("Kontrollerar resultat");
    expect(fasSteg("solving", "Förbättrar balans").find((x) => x.id === "solving")?.label).toBe("Förbättrar balans");
    for (const label of [...s.map((x) => x.label), "Förbättrar balans"]) {
      expect(vcTextArRen(label)).toBe(true);
    }
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

  const job = {
    id: "job-1",
    inputHash: "abc",
    underlagHash: "u1",
    started: "2026-08-03T00:00:00.000Z",
    phase: "solving",
    phaseText: "Skapar balans",
  };

  it("okänt jobb/404 avslutar polling och raderar inte Balans", () => {
    const b = hanteraHamtaJobbSvar(
      { ok: false, status: "404", meddelande: "Beräkningen hittades inte. Den kan ha försvunnit vid omstart." },
      job,
      "u1",
    );
    expect(b.stoppa).toBe(true);
    expect(b.kallaKlart).toBe(false);
    expect(b.bevaraBalans).toBe(true);
    expect(b.nasta.phase).toBe("failed");
    expect(b.nasta.phaseText).toBe(AVBRUTEN_JOBB_TEXT);
  });

  it("POST-hash är samma som poll jämför mot, inte payload-hash", () => {
    const payload = {
      workplace: { start: "2026-08-03", end: "2026-08-30" },
      employees: [{ id: "e1", ssg: 100 }],
      interventions: [1, 2, 3],
      rules: { jourFloor: 1 },
    };
    const api = { underlagFingeravtryck: () => "vy-fingeravtryck" };
    const postHash = underlagHashVidStart(api, payload);
    const pollHash = api.underlagFingeravtryck();
    expect(postHash).toBe(pollHash);
    expect(postHash).not.toBe(underlagFingeravtryckFranPayload(payload));
  });

  it("completed med oförändrat underlag är inte stale och appliceras", () => {
    const b = hanteraHamtaJobbSvar(
      {
        ok: true,
        status: "completed",
        inputHash: "abc",
        phase: "completed",
        outcome: "balans_klar",
        result: { ok: true, status: "FEASIBLE" },
      },
      job,
      "u1",
    );
    expect(b.nasta.stale).toBe(false);
    expect(b.kallaKlart).toBe(true);
    expect(b.stoppa).toBe(true);
  });

  it("stale underlag efter reload behålls på känt jobb", () => {
    const b = hanteraHamtaJobbSvar(
      {
        ok: true,
        status: "completed",
        inputHash: "abc",
        phase: "completed",
        phaseText: "Balans klar",
        outcome: "balans_klar",
        result: { ok: true, status: "FEASIBLE" },
      },
      job,
      "annat-underlag",
    );
    expect(b.nasta.stale).toBe(true);
    expect(b.nasta.inputHash).toBe("abc");
    expect(b.kallaKlart).toBe(false);
    expect(b.stoppa).toBe(true);
    expect(b.bevaraBalans).toBe(true);
  });

  it("avbrutet jobb utan resultat inför inte och raderar inte Balans", () => {
    const b = hanteraHamtaJobbSvar(
      {
        ok: true,
        status: "failed",
        phase: "failed",
        phaseText: "Beräkningen avbröts när tjänsten startades om. Skapa balans igen.",
        outcome: "tekniskt_fel",
      },
      job,
      "u1",
    );
    expect(b.stoppa).toBe(true);
    expect(b.kallaKlart).toBe(false);
    expect(b.bevaraBalans).toBe(true);
  });
});
