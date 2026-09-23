import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { readFileSync } from "fs";
import {
  klassificeraExcel,
  beslutaImportvag,
  SCHEMA_OMDIRIGERAD,
  KUNDBEHOV_OMDIRIGERAD,
  OKAND_UNDERLAG_FEL,
} from "@/lib/bb/filtyp";

const wb = (p: string) => XLSX.read(readFileSync(p), { type: "buffer" });
const sekoia = wb("qa/fixtures/Galaxen_sekoia.xlsx");
const medvind = wb("qa/fixtures/Schema_galaxen.xlsx");

function okandBok() {
  const bok = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(bok, XLSX.utils.aoa_to_sheet([["Foo", "Bar"], ["1", "2"]]), "Blad1");
  return bok;
}

describe("Feltålig filuppladdning", () => {
  it("Sekoia via Kundbehov → korrekt", () => {
    const k = klassificeraExcel(sekoia);
    expect(k.sekoia?.rows.length).toBe(2541);
    expect(k.medvind).toBeNull();
    expect(beslutaImportvag("kundbehov", k)).toEqual({ slag: "kundbehov", omdirigerad: false });
  });

  it("Medvind via Schema → korrekt", () => {
    const k = klassificeraExcel(medvind);
    expect(k.medvind?.pass.length).toBe(143);
    expect(k.sekoia).toBeNull();
    expect(beslutaImportvag("schema", k)).toEqual({ slag: "schema", omdirigerad: false });
  });

  it("Medvind via Kundbehov → omdirigeras korrekt", () => {
    const k = klassificeraExcel(medvind);
    expect(beslutaImportvag("kundbehov", k)).toEqual({
      slag: "schema",
      omdirigerad: true,
      meddelande: SCHEMA_OMDIRIGERAD,
    });
  });

  it("Sekoia via Schema → omdirigeras korrekt", () => {
    const k = klassificeraExcel(sekoia);
    expect(beslutaImportvag("schema", k)).toEqual({
      slag: "kundbehov",
      omdirigerad: true,
      meddelande: KUNDBEHOV_OMDIRIGERAD,
    });
  });

  it("okänd Excel-fil → begripligt fel", () => {
    const k = klassificeraExcel(okandBok());
    expect(k.sekoia).toBeNull();
    expect(k.medvind).toBeNull();
    const b = beslutaImportvag("kundbehov", k);
    expect(b.slag).toBe("okand");
    expect(b.meddelande).toBe(OKAND_UNDERLAG_FEL);
    expect(b.meddelande).not.toMatch(/kolumn|Schemarad|Planerad start|Datum, Kund/i);
    expect(beslutaImportvag("schema", k).slag).toBe("okand");
  });
});
