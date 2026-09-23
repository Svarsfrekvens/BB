/**
 * Klassificerar Excel-underlag med befintliga parsers.
 * Ingen egen parsning – bara vilket importflöde som ska köras.
 */
import { parseSekoiaRapport } from "./sekoia";
import { parseMedvind } from "./medvind";

export type Importvag = "kundbehov" | "schema";

export const SCHEMA_OMDIRIGERAD =
  "Det här är en schemafil. Vi har lagt den under Medarbetare & schema.";
export const KUNDBEHOV_OMDIRIGERAD =
  "Det här är ett kundbehov. Vi har lagt det under Kundbehov.";
export const OKAND_UNDERLAG_FEL =
  "Vi kunde inte läsa filen som kundbehov eller personalschema. Använd en Sekoia-export för kundernas behov eller en Medvind-export för schemat.";

export function klassificeraExcel(wb: unknown) {
  let sekoia: ReturnType<typeof parseSekoiaRapport> | null = null;
  let medvind: ReturnType<typeof parseMedvind> = null;
  try {
    sekoia = parseSekoiaRapport(wb);
  } catch {
    sekoia = null;
  }
  try {
    medvind = parseMedvind(wb);
  } catch {
    medvind = null;
  }
  const sekoiaOk = Boolean(sekoia && Array.isArray(sekoia.rows) && sekoia.rows.length);
  const medvindOk = Boolean(medvind && Array.isArray(medvind.pass) && medvind.pass.length);
  return {
    sekoia: sekoiaOk ? sekoia : null,
    medvind: medvindOk ? medvind : null,
  };
}

export function beslutaImportvag(
  vald: Importvag,
  klass: { sekoia: unknown; medvind: unknown },
): { slag: Importvag | "okand"; omdirigerad: boolean; meddelande?: string } {
  if (vald === "kundbehov") {
    if (klass.sekoia) return { slag: "kundbehov", omdirigerad: false };
    if (klass.medvind) return { slag: "schema", omdirigerad: true, meddelande: SCHEMA_OMDIRIGERAD };
  } else {
    if (klass.medvind) return { slag: "schema", omdirigerad: false };
    if (klass.sekoia) return { slag: "kundbehov", omdirigerad: true, meddelande: KUNDBEHOV_OMDIRIGERAD };
  }
  return { slag: "okand", omdirigerad: false, meddelande: OKAND_UNDERLAG_FEL };
}
