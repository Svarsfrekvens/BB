import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { parseMedvind } from "@/lib/bb/medvind";

describe("Medvind-celler", () => {
  it("tre pass i samma cell ger tre pass, ett jour", () => {
    const cell = "15:00-23:00  Ar\n23:00-06:30  Jo\n06:30-10:00  Ar";
    const wb = XLSX.utils.book_new();
    const grid = [
      ["Schemarad", "Avtalsområde", "Placerad", "Övrigt", "Mån"],
      ["", "", "", "", "3/8"],
      ["Topas 70% tillsv", "", "Topas", "", cell],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(grid), "Medvind");
    const sk = parseMedvind(wb);
    expect(sk).toBeTruthy();
    expect(sk!.pass).toHaveLength(3);
    expect(sk!.pass.filter((p) => p.jour)).toHaveLength(1);
    expect(sk!.pass.map((p) => p.kod)).toEqual(["Ar", "Jo", "Ar"]);
  });

  it("rad 'Vakanta jourer / Ingen placerad' blir vikarie", () => {
    const wb = XLSX.utils.book_new();
    const grid = [
      ["Schemarad", "Avtalsområde", "Placerad", "Övrigt", "Mån"],
      ["", "", "", "", "3/8"],
      ["Vakanta jourer", "", "Ingen placerad", "", "23:00-06:30  Jo"],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(grid), "Medvind");
    const sk = parseMedvind(wb);
    expect(sk).toBeTruthy();
    expect(sk!.medarbetare.length).toBeGreaterThanOrEqual(1);
    expect(sk!.medarbetare.every((m) => m.vikarie)).toBe(true);
    expect(sk!.pass.every((p) => p.vikarie)).toBe(true);
  });

  it("grad läses ur 'Topas 70% tillsv'", () => {
    const wb = XLSX.utils.book_new();
    const grid = [
      ["Schemarad", "Avtalsområde", "Placerad", "Övrigt", "Mån"],
      ["", "", "", "", "3/8"],
      ["Topas 70% tillsv", "", "Topas", "", "07:00-16:00  Ar"],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(grid), "Medvind");
    const sk = parseMedvind(wb);
    expect(sk!.medarbetare.find((m) => m.namn === "Topas")?.grad).toBe(70);
  });
});
