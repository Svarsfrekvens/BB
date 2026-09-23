/** Navigation för det linjära arbetsflödet. Ingen beräkning. */

export type Flodeslage = {
  harKundrader: boolean;
  kundGodkand: boolean;
  harSchema: boolean;
  schemaGodkand: boolean;
  harBalans: boolean;
  balansGodkand: boolean;
};

export function nastaFlodesTab(d: Flodeslage): string {
  if (!d.harKundrader) return "uppladdning";
  if (!d.kundGodkand) return "kundbehov";
  if (!d.harSchema) return "uppladdning";
  if (!d.schemaGodkand) return "medarbetare";
  if (!d.harBalans) return "planering";
  if (!d.balansGodkand) return "foreefter";
  return "nyckeltal";
}

export function hemAteruppta(d: Flodeslage): { tab: string; label: string } {
  if (!d.harKundrader) return { tab: "uppladdning", label: "Ladda upp kundbehov" };
  if (!d.kundGodkand) return { tab: "kundbehov", label: "Granska kundunderlag" };
  if (!d.harSchema) return { tab: "uppladdning", label: "Ladda upp schema" };
  if (!d.schemaGodkand) return { tab: "medarbetare", label: "Granska medarbetare & villkor" };
  if (!d.harBalans) return { tab: "planering", label: "Fortsätt till planering" };
  if (!d.balansGodkand) return { tab: "foreefter", label: "Öppna Före vs Balans" };
  return { tab: "nyckeltal", label: "Följ upp utfall" };
}

export function flodesTabAlias(id: string): string {
  if (id === "resultat" || id === "schemaforslag") return "foreefter";
  if (id === "skapa") return "forutsattningar";
  return id;
}
