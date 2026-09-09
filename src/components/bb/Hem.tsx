import type { VyProps } from "@/lib/bb/vy";
import { Oversikt } from "./Oversikt";
import { Uppladdning } from "./Uppladdning";

/** Hem visar startflödet tills underlagen är godkända och blir därefter dashboard. */
export function Hem(props: VyProps) {
  return props.api.underlag().godkand.allt ? <Oversikt {...props} /> : <Uppladdning {...props} />;
}
