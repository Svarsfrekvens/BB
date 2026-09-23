import { describe, it, expect, vi } from "vitest";

vi.mock("@/lib/bb/korBemanningsbalans", () => ({
  korBemanningsbalans: vi.fn(),
}));

import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { resursbristProps } from "@/components/bb/ResursbristPanel";

describe("Skapa balans igen efter extra resurs", () => {
  it("anropar motorn, inte lokal skapaBalans", () => {
    const skapaBalans = vi.fn();
    const api = {
      extraResurser: () => [],
      underlag: () => ({ schema: { vakantaPass: 0 } }),
      motorResultat: () => null,
      sparaExtraResurs: () => ({ ok: true, fel: [] }),
      taBortExtraResurs: () => undefined,
      skapaBalans,
    };
    const state = { id: "v1" };
    resursbristProps(api as never, state as never).onSkapaBalansIgen?.();
    expect(korBemanningsbalans).toHaveBeenCalledWith({ api, state });
    expect(skapaBalans).not.toHaveBeenCalled();
  });
});
