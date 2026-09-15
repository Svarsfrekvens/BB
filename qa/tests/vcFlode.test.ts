import { describe, it, expect } from "vitest";
import {
  FORE_EFTER_NYCKLAR,
  KUNDNARA_FORKLARING,
  KAPACITET_FORKLARING,
  MEDARBETARE_ANDRAD_TEXT,
  PROCESS_STEG,
  PROCESS_HANDLINGAR,
  TIDSLINJE_ORDNING,
  TACKT_BEHOV_FORKLARING,
  TRE_OMRADEN_RUBRIKER,
  VC_FORBJUDNA_ORD,
  behorighetEtikett,
  behorighetLage,
  berakningsKallaText,
  filtreraJamforRader,
  genomsnittligSsgPct,
  getBemanningsbalansReadiness,
  getTidslage,
  hemHuvudCta,
  hemStatusText,
  balansKanGodkannas,
  effektPilFranForandring,
  MATCHNING_FORMEL,
  UNDERKAPACITET_FORMEL,
  OVERKAPACITET_FORMEL,
  raknaSaknadeKompetenskrav,
  visningEffekt,
  konfigureratKundnaraMalPct,
  behoverUppmarksamhet,
  jamforTon,
  kundUnderlagStatus,
  lasMotorSummary,
  oversiktVisaLage,
  processStegLagen,
  readinessFranApi,
  skapaBalansHinder,
  ssgUtnyttjandePct,
  timmarEllerTomt,
  vcStatusText,
  visningsNamnVerksamhet,
} from "@/lib/bb/vcFlode";
import { kanStartaFranEttKlick } from "@/lib/bb/korBemanningsbalans";
import { byggMotorPayload } from "@/lib/bb/motorPayload";
import { DEFAULT_WORK_TIME_MODEL_ID, STANDARD_WORK_TIME_MODELS } from "@/lib/bb/arbetstid";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const rot = join(dirname(fileURLToPath(import.meta.url)), "../..");

function klarIndata(extra: Partial<Parameters<typeof getBemanningsbalansReadiness>[0]> = {}) {
  return {
    harKundrader: true,
    harSchema: true,
    kundGodkand: true,
    schemaGodkand: true,
    medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: true }],
    ...extra,
  };
}

describe("processsteg", () => {
  it("har ett sammanhängande VC-flöde med pilar", () => {
    expect(PROCESS_STEG.map((s) => s.label)).toEqual([
      "Före",
      "Skapa balans",
      "Balans",
      "Granska balans",
      "Godkänn balans",
      "Utfall",
    ]);
    expect(PROCESS_STEG.filter((s) => s.typ === "lage").map((s) => s.label)).toEqual([...TIDSLINJE_ORDNING]);
    expect(PROCESS_STEG.filter((s) => s.typ === "handling").map((s) => s.label)).toEqual([...PROCESS_HANDLINGAR]);
    const src = readFileSync(join(rot, "src/components/bb/ProcessFlode.tsx"), "utf8");
    expect(src).toContain("→");
    expect(src).not.toMatch(/Progress/);
    expect(src).toContain("Ej påbörjad");
    expect(src).toContain("Pågående");
    expect(src).toContain("Klar");
    expect(src).toContain("Varning");
    expect(src).toContain("Blockerad");
    expect(src).toContain("data-tidslinje");
    expect(src).toContain("Före → Balans → Utfall");
  });

  it("visar processrad endast i skalet, inte på Hem", () => {
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    const skal = readFileSync(join(rot, "src/components/bb/Skal.tsx"), "utf8");
    expect(hem).not.toContain("ProcessFlode");
    expect(skal).toContain("<ProcessFlode");
  });

  it("sätter blockerad när skapa inte får köras", () => {
    const r = getBemanningsbalansReadiness({
      harKundrader: false,
      harSchema: false,
      kundGodkand: false,
      schemaGodkand: false,
      medarbetare: [],
    });
    const steg = processStegLagen({
      aktivTab: "hem",
      readiness: r,
      harResultat: false,
      harVarning: false,
    });
    expect(steg.find((s) => s.id === "skapa")?.lage).toBe("blockerad");
    expect(steg.find((s) => s.id === "fore")?.lage).toBe("ej");
    expect(steg.find((s) => s.id === "balans")?.lage).toBe("ej");
  });

  it("tom medarbetarlista är ej påbörjad, aldrig klar", () => {
    const r = getBemanningsbalansReadiness({
      harKundrader: true,
      harSchema: false,
      kundGodkand: true,
      schemaGodkand: false,
      medarbetare: [],
    });
    expect(r.delar.medarbetare).toBe("ej");
    expect(r.harMedarbetare).toBe(false);
    expect(r.ready).toBe(false);
  });

  it("varnar på granska när resultat finns med varning", () => {
    const steg = processStegLagen({
      aktivTab: "resultat",
      readiness: getBemanningsbalansReadiness(klarIndata()),
      harResultat: true,
      harVarning: true,
    });
    expect(steg.find((s) => s.id === "resultat")?.lage).toBe("varning");
  });
});

describe("en enda readiness-selector", () => {
  it("Hem-CTA och motoranrop använder samma funktion", () => {
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    const kor = readFileSync(join(rot, "src/lib/bb/korBemanningsbalans.ts"), "utf8");
    expect(hem).toContain("readinessFranApi");
    expect(hem).toContain("korBemanningsbalans");
    expect(kor).toContain("readinessFranApi");
    expect(kor).toContain("if (!r.ready) return \"blockerad\"");
  });

  it("är inaktiv utan godkänt kundbehov", () => {
    const r = getBemanningsbalansReadiness(klarIndata({ kundGodkand: false }));
    expect(r.ready).toBe(false);
    expect(r.blockingReasons).toContain("Kundbehovet är inte godkänt");
    const h = skapaBalansHinder({
      kundGodkand: false,
      schemaGodkand: true,
      harUnderlag: true,
      medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: true }],
    });
    expect(h.aktiv).toBe(false);
  });

  it("räknar medarbetare utan arbetstidsmodell", () => {
    const r = getBemanningsbalansReadiness(
      klarIndata({
        medarbetare: [{ namn: "Anna" }, { namn: "Bo" }, { namn: "Cia", workTimeModelId: "helgfri-40", nattbehorig: true }],
        defaultWorkTimeModelId: "",
        workTimeModels: [],
      }),
    );
    expect(r.ready).toBe(false);
    expect(r.blockingReasons.some((s) => s.includes("2 medarbetare saknar arbetstidsmodell"))).toBe(true);
  });

  it("ärver verksamhetsdefault när individuell modell saknas", () => {
    const r = getBemanningsbalansReadiness(
      klarIndata({
        medarbetare: [{ namn: "Anna" }, { namn: "Bo", workTimeModelId: "helgfri-40" }],
        defaultWorkTimeModelId: DEFAULT_WORK_TIME_MODEL_ID,
        workTimeModels: STANDARD_WORK_TIME_MODELS,
      }),
    );
    expect(r.ready).toBe(true);
    expect(r.blockingReasons).toEqual([]);
    expect(r.delar.medarbetare).toBe("klar");
  });

  it("blockerar när varken individuell modell eller giltig verksamhetsdefault finns", () => {
    const r = getBemanningsbalansReadiness(
      klarIndata({
        medarbetare: [{ namn: "Anna" }],
        defaultWorkTimeModelId: "finns-inte",
        workTimeModels: STANDARD_WORK_TIME_MODELS,
      }),
    );
    expect(r.ready).toBe(false);
    expect(r.blockingReasons.some((s) => s.includes("saknar arbetstidsmodell"))).toBe(true);
  });

  it("datumstyrt fönster räknas som individuell modell före default", () => {
    const r = getBemanningsbalansReadiness(
      klarIndata({
        medarbetare: [{ namn: "Anna", workTimeWindows: [{ start: "2026-08-01", end: "2026-08-31", modelId: "standig-natt-36-20" }] }],
        defaultWorkTimeModelId: "",
        workTimeModels: [],
      }),
    );
    expect(r.ready).toBe(true);
  });

  it("readinessFranApi använder verksamhetens standardmodell så Galaxen-import inte blockeras", () => {
    const api = {
      underlag: () => ({ godkand: { kund: true, schema: true }, sekoia: {}, schema: {} }),
      medarbetare: () => [{ namn: "Topas" }, { namn: "Turmalin" }, { namn: "Jade" }, { namn: "Bärnsten" }, { namn: "Ametist" }],
    };
    const r = readinessFranApi(api);
    expect(r.ready).toBe(true);
    expect(r.blockingReasons).toEqual([]);
  });

  it("natt unknown blockerar inte och defaultas inte till ja", () => {
    const r = getBemanningsbalansReadiness(
      klarIndata({ medarbetare: [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: null }] }),
    );
    expect(r.ready).toBe(true);
    expect(r.blockingReasons).not.toContain("Nattbehörighet saknas");
    expect(behorighetEtikett(null)).toBe("Ej angivet");
    expect(behorighetLage(undefined)).toBe("okand");
    expect(behorighetEtikett(true)).toBe("Ja");
  });

  it("är aktiv när underlaget räcker, och då startar ett klick", () => {
    const r = getBemanningsbalansReadiness(klarIndata());
    expect(r.ready).toBe(true);
    expect(r.blockingReasons).toEqual([]);
    const api = {
      underlag: () => ({ godkand: { kund: true, schema: true }, sekoia: {}, schema: {} }),
      medarbetare: () => [{ namn: "Anna", workTimeModelId: "helgfri-40", nattbehorig: true as const }],
      harBalans: () => false,
    };
    expect(readinessFranApi(api).ready).toBe(true);
    expect(kanStartaFranEttKlick(api as never)).toBe(true);
  });

  it("status förändrad efter relevant ändring blockerar CTA", () => {
    const r = getBemanningsbalansReadiness(klarIndata({ medarbetareAndradSedanGodkannande: true }));
    expect(r.ready).toBe(false);
    expect(r.delar.medarbetare).toBe("forandrad");
    expect(r.blockingReasons).toContain(MEDARBETARE_ANDRAD_TEXT);
  });
});

describe("godkännanden", () => {
  it("import godkänner inte kundunderlag automatiskt", () => {
    const src = readFileSync(join(rot, "src/lib/bb/app.ts"), "utf8");
    const start = src.indexOf("function approveImport()");
    const end = src.indexOf("function ", start + 10);
    const fn = src.slice(start, end);
    expect(fn).toMatch(/kundGodkand = false/);
    expect(fn).not.toMatch(/kundGodkand = true/);
  });
});

describe("KPI-benämningar", () => {
  it("genomsnittlig SSG är inte SSG-utnyttjande", () => {
    const snitt = genomsnittligSsgPct([{ grad: 80 }, { grad: 90 }]);
    const utnytt = ssgUtnyttjandePct(null, null);
    expect(snitt).toBe(85);
    expect(utnytt).toBeNull();
    const tre = readFileSync(join(rot, "src/components/bb/TreOmraden.tsx"), "utf8");
    expect(tre).toMatch(/ssgUtnyttjande/);
    expect(tre).not.toContain("etikett: \"Genomsnittlig SSG\"");
  });

  it("vakanta rader är inte vakanta timmar och vikarieantal inte vikarietimmar", () => {
    expect(timmarEllerTomt(null).saknas).toBe(true);
    expect(timmarEllerTomt(12).text).toMatch(/12/);
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    expect(hem).not.toMatch(/vakanta rader/);
    expect(hem).not.toMatch(/vikarier`/);
  });
});

describe("natt/jour i payload", () => {
  it("unknown skickas inte som behörig", () => {
    const p = byggMotorPayload({
      rader: [],
      medarbetare: [
        {
          namn: "Okand",
          vakant: false,
          vikarie: false,
          grad: 100,
          samordnare: false,
          delegering: null,
          jour: null,
          nattbehorig: null,
          passprofil: "blandat",
          helg: "varannan",
          tidigastStart: "06:30",
          senastSlut: "23:00",
          maxDagarIFoljd: 5,
          franvaro: "ingen",
          timkostnad: 270,
          anstallning: "manad",
          workTimeModelId: "helgfri-40",
        },
      ],
      from: "2026-01-05",
      dagar: 7,
      timkostnad: 270,
    });
    const emp = (p.payload.employees as { night: boolean; skills: string[] }[])[0];
    expect(emp?.night).toBe(false);
    expect(emp?.skills || []).not.toContain("delegering");
  });
});

describe("kundnära och täckt behov", () => {
  it("har skilda förklaringar", () => {
    expect(KUNDNARA_FORKLARING).toMatch(/schemalagd kundnära/);
    expect(TACKT_BEHOV_FORKLARING).toMatch(/bemannat kundbehov/);
    expect(KUNDNARA_FORKLARING).not.toBe(TACKT_BEHOV_FORKLARING);
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    expect(hem).toContain("KUNDNARA_FORKLARING");
    expect(hem).toContain("TACKT_BEHOV_FORKLARING");
    expect(KAPACITET_FORKLARING).toMatch(/Överkapacitet/);
  });
});

describe("tekniska motorord", () => {
  it("visas inte i VC-vyn", () => {
    const filer = [
      "src/components/bb/Hem.tsx",
      "src/components/bb/Skal.tsx",
      "src/components/bb/Kundbehov.tsx",
      "src/components/bb/Medarbetare.tsx",
      "src/components/bb/Resultat.tsx",
      "src/components/bb/TreOmraden.tsx",
      "src/components/bb/ResursbristPanel.tsx",
      "src/components/bb/Uppladdning.tsx",
    ];
    for (const f of filer) {
      const src = readFileSync(join(rot, f), "utf8");
      for (const ord of VC_FORBJUDNA_ORD) {
        expect(src.toLowerCase(), `${f} innehåller ${ord}`).not.toContain(ord.toLowerCase());
      }
    }
    expect(vcStatusText("INFEASIBLE")).not.toMatch(/INFEASIBLE/);
    expect(berakningsKallaText("lokal")).toBe("Förhandsberäkning i appen");
    expect(berakningsKallaText("motor")).toBe("Bemanningsbalans skapad med motor");
    expect(visningsNamnVerksamhet("")).toBe("Verksamhet ej namngiven");
    expect(visningsNamnVerksamhet("Ny verksamhet")).toBe("Verksamhet ej namngiven");
    expect(visningsNamnVerksamhet("Galaxen")).toBe("Galaxen");
  });
});

describe("summary-adapter", () => {
  it("mappar motorns summary-fält utan egen solverdiagnostik", () => {
    const s = lasMotorSummary({
      summary: {
        status: "FEASIBLE",
        coveragePercent: 100,
        customerNearPercent: 32.1,
        cost: 1234500,
        hardViolations: [{ rule: "rest", message: "vila" }],
        warnings: [{ message: "natt" }],
        changedShiftCount: 4,
        lockedShiftCount: 2,
        explanationSummary: "Täckning först.",
        performanceSummary: "9s",
      },
    });
    expect(s).toMatchObject({
      status: "FEASIBLE",
      coveragePercent: 100,
      customerNearPercent: 32.1,
      cost: 1234500,
      changedShiftCount: 4,
      lockedShiftCount: 2,
      explanationSummary: "Täckning först.",
    });
    expect(s?.hardViolations).toHaveLength(1);
    expect(s?.warnings).toHaveLength(1);
    expect(vcStatusText("INFEASIBLE")).not.toMatch(/INFEASIBLE/);
    expect(vcStatusText("FEASIBLE")).toMatch(/giltigt/i);
  });
});

describe("Rätt resurser i rätt tid", () => {
  it("används som rubrik, inte Ekonomi", () => {
    expect(TRE_OMRADEN_RUBRIKER).toEqual(["Kundnära tid", "Hållbara scheman", "Rätt resurs i rätt tid"]);
    expect(TRE_OMRADEN_RUBRIKER.join(" ")).not.toMatch(/Ekonomi/);
    const tre = readFileSync(join(rot, "src/components/bb/TreOmraden.tsx"), "utf8");
    expect(tre).toContain("TRE_OMRADEN_RUBRIKER");
    expect(tre).toContain("lg:grid-cols-3");
    expect(tre).toContain('data-huvudomraden="3"');
    const eko = readFileSync(join(rot, "src/components/bb/Ekonomi.tsx"), "utf8");
    expect(eko).toContain("Rätt resurs i rätt tid");
  });
});

describe("före/efter och polaritet", () => {
  it("visar Före → Balans-mått med underkapacitet under matchning", () => {
    const rader = filtreraJamforRader([
      { namn: "Täckt behov", fore: "80 %", efter: "90 %", forandring: "+10 %", riktning: "upp" },
      { namn: "Personalkostnad", fore: "10", efter: "9", forandring: "−1", riktning: "upp" },
      { namn: "Planerade personaltimmar", fore: "100", efter: "80", forandring: "−20", riktning: "upp" },
      { namn: "Överbemanning", fore: "10", efter: "4", forandring: "−6", riktning: "upp" },
      { namn: "Matchning mot behov", fore: "63 %", efter: "67 %", forandring: "+4 %", riktning: "upp" },
      { namn: "Otäckt dimensionerande resursbehov", fore: "372", efter: "334", forandring: "−38", riktning: "upp" },
      { namn: "Obemannat kundbehov", fore: "100", efter: "50", forandring: "−50", riktning: "upp" },
    ]);
    expect(rader.map((r) => r.namn)).toEqual([
      "Planerade personaltimmar",
      "Matchning mot behov",
      "Underkapacitet",
      "Överkapacitet",
      "Täckt behov",
      "Personalkostnad",
    ]);
    expect(rader.find((r) => r.namn === "Underkapacitet")?.underMatchning).toBe(true);
    expect(rader.find((r) => r.namn === "Överkapacitet")?.underMatchning).toBe(true);
    expect(rader.map((r) => r.namn)).not.toContain("Obemannat kundbehov");
    expect(FORE_EFTER_NYCKLAR).toContain("Täckt behov");
    expect(FORE_EFTER_NYCKLAR).toContain("Matchning mot behov");
  });

  it("markerar inte lägre bemanning som bra när täckningen sjunker", () => {
    expect(jamforTon({ namn: "Överkapacitet", riktning: "upp", tackningSank: true })).toBe("varn");
    expect(jamforTon({ namn: "Täckt behov", riktning: "upp", tackningSank: false })).toBe("bra");
    expect(jamforTon({ namn: "Täckt behov", riktning: "ner", tackningSank: true })).toBe("varn");
  });

  it("effektpilar följer talets riktning, inte förbättring", () => {
    expect(effektPilFranForandring("−9 720 kr")).toBe("ner");
    expect(effektPilFranForandring("+4 %")).toBe("upp");
    expect(effektPilFranForandring("–")).toBe("lika");
  });
});

describe("varningar, hårda brott, ändrade och låsta pass", () => {
  it("läser counts från summary", () => {
    const s = lasMotorSummary({
      summary: {
        status: "FEASIBLE",
        hardViolations: [{}, {}],
        warnings: [{}],
        changedShiftCount: 7,
        lockedShiftCount: 3,
        cost: 0,
      },
    });
    expect(s?.hardViolations).toHaveLength(2);
    expect(s?.warnings).toHaveLength(1);
    expect(s?.changedShiftCount).toBe(7);
    expect(s?.lockedShiftCount).toBe(3);
  });
});

describe("tomma, laddande och fel-lägen", () => {
  it("väljer visningsläge utan att räkna om KPI", () => {
    expect(oversiktVisaLage({ laddar: true })).toBe("laddar");
    expect(oversiktVisaLage({ fel: "saknas" })).toBe("fel");
    expect(oversiktVisaLage({ tom: true })).toBe("tom");
    expect(oversiktVisaLage({})).toBe("klar");
  });

  it("kundunderlag visar klar, kompletteras eller förändrad", () => {
    expect(kundUnderlagStatus({ godkand: true }).text).toBe("Klar");
    expect(kundUnderlagStatus({ godkand: false }).text).toBe("Behöver kompletteras");
    expect(kundUnderlagStatus({ godkand: true, redigerad: true }).text).toBe("Förändrad sedan senaste godkännande");
  });
});

describe("Före / Balans / Utfall", () => {
  it("väljer läge utan att blanda plan och utfall", () => {
    expect(getTidslage({ harBalans: false })).toBe("fore");
    expect(getTidslage({ harBalans: true })).toBe("balans");
    expect(getTidslage({ harBalans: true, harUtfall: true })).toBe("utfall");
  });

  it("har en CTA per läge", () => {
    expect(hemHuvudCta({ lage: "fore", ready: true, godkannbar: false }).label).toBe("Skapa balans");
    expect(hemHuvudCta({ lage: "fore", ready: true, godkannbar: false }).disabled).toBe(false);
    expect(hemHuvudCta({ lage: "balans", ready: true, godkannbar: false }).label).toBe("Granska balans");
    expect(hemHuvudCta({ lage: "balans", ready: true, godkannbar: false }).disabled).toBe(false);
    expect(hemHuvudCta({ lage: "balans", ready: true, godkannbar: true }).label).toBe("Godkänn balans");
    expect(hemHuvudCta({ lage: "utfall", ready: true, godkannbar: true }).label).toBe("Följ upp utfall");
    expect(hemHuvudCta({ lage: "fore", ready: true, godkannbar: false, pagaende: true }).label).toBe("Visa status");
  });

  it("kan skapa balans i Före trots täckt behov under 100 %, hårda regelbrott och underkapacitet", () => {
    const src = readFileSync(join(rot, "src/lib/bb/vcFlode.ts"), "utf8");
    const start = src.indexOf("export function getBemanningsbalansReadiness");
    const end = src.indexOf("export function skapaBalansHinder");
    const fn = src.slice(start, end);
    expect(fn).not.toMatch(/tacktBehov|tackningPct|hardViolation|underkapacitet|overkapacitet|obemannatH/);
    expect(getBemanningsbalansReadiness(klarIndata()).ready).toBe(true);
    expect(hemHuvudCta({ lage: "fore", ready: true, godkannbar: false }).disabled).toBe(false);
    const steg = processStegLagen({
      aktivTab: "hem",
      readiness: getBemanningsbalansReadiness(klarIndata()),
      harResultat: false,
      harVarning: true,
    });
    expect(steg.find((s) => s.id === "skapa")?.lage).not.toBe("blockerad");
    expect(steg.map((s) => s.label).join(" → ")).toBe(
      "Före → Skapa balans → Balans → Granska balans → Godkänn balans → Utfall",
    );
  });

  it("kan inte godkänna Balans under 100 % täckt behov, med hårda regelbrott eller saknad kompetens", () => {
    expect(balansKanGodkannas({ tacktBehovPct: 88.7, hardViolations: 0 }).ok).toBe(false);
    expect(balansKanGodkannas({ tacktBehovPct: 99.74, hardViolations: 0 }).ok).toBe(false);
    expect(balansKanGodkannas({ tacktBehovPct: 100, hardViolations: 1 }).ok).toBe(false);
    expect(balansKanGodkannas({ tacktBehovPct: 100, hardViolations: 0 }).ok).toBe(true);
    expect(balansKanGodkannas({ tacktBehovPct: 99.74, hardViolations: 0 }).reasons[0]).toMatch(/kundbehov återstår/);
    expect(balansKanGodkannas({ tacktBehovPct: 100, hardViolations: 0, saknadeKompetenskrav: 1 }).ok).toBe(false);
    expect(raknaSaknadeKompetenskrav([{ message: "Insatsen kräver kompetens som saknas" }])).toBe(1);
  });

  it("håller Täckt behov och Kundnära tid isär", () => {
    expect(TACKT_BEHOV_FORKLARING).not.toBe(KUNDNARA_FORKLARING);
    expect(TACKT_BEHOV_FORKLARING).toMatch(/bemannat kundbehov/);
    expect(KUNDNARA_FORKLARING).toMatch(/schemalagd kundnära/);
  });

  it("dokumenterar matchning och kapacitet utan att ändra formeln", () => {
    expect(MATCHNING_FORMEL.kod).toContain("obemannatH / dimH");
    expect(MATCHNING_FORMEL.tidsmassigMatchning).toBe(true);
    expect(MATCHNING_FORMEL.overlapparTacktBehov).toBe(false);
    expect(UNDERKAPACITET_FORMEL.falt).toContain("obemannatH");
    expect(OVERKAPACITET_FORMEL.anvanderDimensionerandeKurva).toBe(false);
    expect(OVERKAPACITET_FORMEL.asymmetriUtvarderasEfterAxelsberg).toBe(true);
  });

  it("Hem har tre huvudområden och CTA, inte underbemanning som etikett för dimensionerande gap", () => {
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    const tre = readFileSync(join(rot, "src/components/bb/TreOmraden.tsx"), "utf8");
    expect(hem).toContain("data-cta={cta.id}");
    expect(hem).toContain("data-statusrad");
    expect(tre).toContain("Matchning mot behov");
    expect(tre).toContain("↳");
    expect(tre).not.toContain("Obemannat behov");
  });

  it("tar bort äldre Före/Efter-begrepp ur synlig UI", () => {
    const filer = [
      "src/components/bb/ForeEfter.tsx",
      "src/components/bb/Motor.tsx",
      "src/components/bb/Oversikt.tsx",
      "src/components/bb/Hem.tsx",
      "src/components/bb/Uppfoljning.tsx",
      "src/components/bb/ProcessFlode.tsx",
    ];
    for (const f of filer) {
      const src = readFileSync(join(rot, f), "utf8");
      expect(src, f).not.toContain("Underbemanning (obemannat behov)");
      expect(src, f).not.toContain(">Efter<");
      expect(src, f).not.toContain("Överbemanning");
      expect(src, f).not.toContain("Ekonomiskt resultat");
      expect(src, f).not.toMatch(/↑ −/);
      expect(src, f).not.toMatch(/↑ -/);
    }
    const hem = readFileSync(join(rot, "src/components/bb/Hem.tsx"), "utf8");
    expect(hem).not.toMatch(/Målet är 75/);
    expect(hem).not.toContain("|| 0.75");
    expect(hem).toContain("data-nulagekort");
    expect(konfigureratKundnaraMalPct({ varde: 0.75, definition: "Pilotmål" })).toBeNull();
    expect(konfigureratKundnaraMalPct({ varde: 0.8, definition: "Verksamhetsmål" })).toBe(80);
    expect(visningEffekt("−36,0 h")).toEqual({ pil: "ner", text: "36,0 h" });
    expect(visningEffekt("+7,1 %")).toEqual({ pil: "upp", text: "7,1 %" });
    expect(behoverUppmarksamhet({ hardViolations: 58, underkapacitetH: 1, overkapacitetH: 1, tacktBehovPct: 82.5 }).length).toBeGreaterThan(0);
    const flode = readFileSync(join(rot, "src/components/bb/ProcessFlode.tsx"), "utf8");
    expect(flode).toContain('data-tidslinje="Före → Balans → Utfall"');
    expect(flode).toContain('data-handlingar="inom-tidslinje"');
  });
});
