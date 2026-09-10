import { useSyncExternalStore } from "react";
import { bbVy, REAKT_TABS } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { Oversikt } from "./Oversikt";
import { Hem } from "./Hem";
import { Kundgrupp } from "./Kundgrupp";
import { Verksamhet } from "./Verksamhet";
import { Uppladdning } from "./Uppladdning";
import { SchemaFil } from "./SchemaFil";
import { Medarbetare } from "./Medarbetare";
import { Underlag } from "./Underlag";
import { ForeEfter } from "./ForeEfter";
import { Schemaforslag } from "./Schemaforslag";
import { Kundbehov } from "./Kundbehov";
import { Resursbehov } from "./Resursbehov";
import { Bemanning } from "./Bemanning";
import { Schema } from "./Schema";
import { Ekonomi } from "./Ekonomi";
import { PerKund } from "./PerKund";
import { Atgarder } from "./Atgarder";
import { Datakontroller } from "./Datakontroller";
import { Uppfoljning } from "./Uppfoljning";
import { Intakter } from "./Intakter";
import { Simulering } from "./Simulering";
import { Villkor } from "./Villkor";
import { Installningar } from "./Installningar";
import { SpridBehov } from "./SpridBehov";
import { Motor } from "./Motor";

/** Registret över vyer som ritas av React. Övriga flikar ritas ännu av det
 * gamla presentationslagret i #view. */
const VYER: Record<string, (p: VyProps) => React.ReactNode> = {
  hem: Hem,
  verksamhet: Verksamhet,
  uppladdning: Uppladdning,
  kundgrupp: Kundgrupp,
  schemafil: SchemaFil,
  medarbetare: Medarbetare,
  underlag: Underlag,
  foreefter: ForeEfter,
  schemaforslag: Schemaforslag,
  oversikt: Oversikt,
  kundbehov: Kundbehov,
  resurskurva: Resursbehov,
  personal: Bemanning,
  schema: Schema,
  nyckeltal: Uppfoljning,
  ekonomi: Ekonomi,
  kunder: PerKund,
  atgarder: Atgarder,
  kontroller: Datakontroller,
  intakter: Intakter,
  simulering: Simulering,
  villkor: Villkor,
  installningar: Installningar,
  sprid: SpridBehov,
  motor: Motor,
};

export function Vy() {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  if (!v.api || !v.state || !REAKT_TABS.has(v.tab)) return null;
  const Komponent = VYER[v.tab];
  if (!Komponent) return null;
  return <div className="pt-1">
      <Komponent key={v.tab} d={v.d} state={v.state} api={v.api} />
    </div>;
}
