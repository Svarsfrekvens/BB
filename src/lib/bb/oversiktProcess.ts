/** Visuell processrad för huvudflödet. Ändrar inte PROCESS_STEG som testerna låser. */

import type { ProcessStegLage } from "./vcFlode";
import type { BemanningsbalansReadiness } from "./vcFlode";

export const OVERSIKT_PROCESS = [
  { id: "underlag", label: "Underlag", tab: "uppladdning" },
  { id: "kundbehov", label: "Kundbehov", tab: "kundbehov" },
  { id: "medarbetare", label: "Medarbetare", tab: "medarbetare" },
  { id: "planering", label: "Planering", tab: "planering" },
  { id: "granska", label: "Granska", tab: "forutsattningar" },
  { id: "skapa", label: "Skapa balans", tab: "forutsattningar" },
  { id: "balans", label: "Balans", tab: "foreefter" },
  { id: "utfall", label: "Utfall", tab: "nyckeltal" },
] as const;

export type OversiktProcessSteg = {
  id: string;
  label: string;
  tab: string;
  lage: ProcessStegLage;
};

export function oversigtProcessLagen(d: {
  aktivTab: string;
  readiness: BemanningsbalansReadiness;
  harBalans: boolean;
  harUtfall?: boolean;
  pagaende?: boolean;
}): OversiktProcessSteg[] {
  const tab = d.aktivTab;
  const r = d.readiness;
  const kundKlar = r.delar.kund === "klar";
  const medKlar = r.delar.medarbetare === "klar";
  const underlagKlar = r.harKunddata && (r.delar.schema !== "ej" || !!r.harMedarbetare);
  const redo = r.ready;

  const aktivFranTab = (): string | null => {
    if (tab === "hem" || tab === "oversikt") return null;
    if (tab === "underlag" || tab === "uppladdning" || tab === "kundgrupp" || tab === "schemafil") return "underlag";
    if (tab === "kundbehov") return "kundbehov";
    if (tab === "medarbetare" || tab === "villkor" || tab === "personal") return "medarbetare";
    if (tab === "planering") return "planering";
    if (tab === "forutsattningar" || tab === "kontroller") return "granska";
    if (tab === "motor") return "skapa";
    if (tab === "foreefter" || tab === "schemaforslag" || tab === "resultat") return "balans";
    if (tab === "nyckeltal" || tab === "ekonomi") return "utfall";
    return null;
  };

  const forstaOppet = (): string => {
    if (!underlagKlar) return "underlag";
    if (!kundKlar) return "kundbehov";
    if (!medKlar) return "medarbetare";
    if (!redo) return "granska";
    if (d.pagaende) return "skapa";
    if (!d.harBalans) return "planering";
    if (d.harUtfall) return "utfall";
    return "balans";
  };

  const aktiv = aktivFranTab() || forstaOppet();

  return OVERSIKT_PROCESS.map((steg) => {
    let lage: ProcessStegLage = "ej";
    if (steg.id === "underlag") lage = underlagKlar ? "klar" : "ej";
    else if (steg.id === "kundbehov") lage = kundKlar ? "klar" : r.harKunddata ? "pa" : "ej";
    else if (steg.id === "medarbetare") lage = medKlar ? "klar" : r.harMedarbetare ? "pa" : "ej";
    else if (steg.id === "planering") lage = redo || d.harBalans ? "klar" : medKlar ? "pa" : "ej";
    else if (steg.id === "granska") lage = redo || d.harBalans ? "klar" : medKlar ? "pa" : "ej";
    else if (steg.id === "skapa") {
      if (d.harBalans) lage = "klar";
      else if (d.pagaende) lage = "pa";
      else lage = redo ? "ej" : "ej";
    } else if (steg.id === "balans") lage = d.harBalans ? "klar" : "ej";
    else if (steg.id === "utfall") lage = d.harUtfall ? "klar" : d.harBalans ? "ej" : "ej";

    if (steg.id === aktiv) lage = "pa";
    return { id: steg.id, label: steg.label, tab: steg.tab, lage };
  });
}

export function oversigtProcessTab(id: string) {
  return OVERSIKT_PROCESS.find((s) => s.id === id)?.tab || "uppladdning";
}
