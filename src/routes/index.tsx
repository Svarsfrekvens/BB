import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { Skal } from "@/components/bb/Skal";
import { Vy } from "@/components/bb/Vy";
import { Verksamheter } from "@/components/bb/Verksamheter";
import { ImportGranskning } from "@/components/bb/ImportGranskning";


export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Bemanningsbalans – schema utifrån kundernas behov" },
      {
        name: "description",
        content:
          "Läs in verksamhetens Excel och se kundbehov, resursbehov, bemanning, optimerat schema, uppföljning och ekonomi i ett och samma verktyg.",
      },
      { property: "og:title", content: "Bemanningsbalans – schema utifrån kundernas behov" },
      {
        property: "og:description",
        content:
          "Från kundens behov till ett hållbart schema: kundbehov, resurskurva, bemanning, optimering, nyckeltal och ekonomi.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  useEffect(() => {
    // initBB är idempotent (egen guard i app.ts). Avbryt aldrig importen:
    // effekten körs två gånger i dev och en avbruten-flagga stoppade starten.
    import("../lib/bb/app")
      .then(({ initBB }) => initBB())
      .catch((fel) => console.error("Bemanningsbalans kunde inte starta", fel));
  }, []);

  return (
    <Skal>
      <Verksamheter />
      <ImportGranskning />
      <div id="view" className="hidden" />
      <Vy />

      <input type="file" id="fileInput" accept=".xlsx,.xls" className="hidden" />
      <input type="file" id="nyttFileInput" accept=".xlsx,.xls" className="hidden" />
    </Skal>
  );
}
