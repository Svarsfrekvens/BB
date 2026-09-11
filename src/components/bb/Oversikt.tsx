import type { VyProps } from "@/lib/bb/vy";
import { Hem } from "./Hem";

/** Bemanning under Planera använder samma Före/Balans/Utfall-översikt som Hem. */
export function Oversikt(props: VyProps) {
  return <Hem {...props} />;
}
