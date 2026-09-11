import { ArrowRight, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { VyProps } from "@/lib/bb/vy";
import { berakningsKallaText, lasMotorSummary, readinessFranApi, vcStatusText } from "@/lib/bb/vcFlode";
import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { TreOmraden } from "./TreOmraden";
import { ForeEfter } from "./ForeEfter";

export function Resultat(props: VyProps) {
  const { api, state } = props;
  const summary = lasMotorSummary(api.motorResultat());
  const fe = api.foreEfter();
  const efter = fe?.efter;
  const readiness = readinessFranApi(api);

  if (!api.harBalans()) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <h2 className="text-2xl font-extrabold text-deep">Inget förslag att granska ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          Skapa bemanningsbalans först. Du möter resultatet här, inte schemat.
        </p>
        <Button
          className="mt-6"
          data-cta="skapa-bemanningsbalans"
          disabled={!readiness.ready}
          onClick={() => void korBemanningsbalans({ api, state })}
        >
          <Sparkles /> Skapa bemanningsbalans
        </Button>
      </Card>
    );
  }

  const resurs = {
    intakt: efter ? api.kr(efter.intakt) : "–",
    schemakostnad: efter ? api.kr(efter.kostnad) : summary ? `${Math.round(summary.cost / 100).toLocaleString("sv-SE")} kr` : "–",
    marginal: efter ? api.kr(efter.resultat) : "–",
    overkapacitet: efter ? `${api.h1(efter.overkapacitetH)} h` : "–",
    underkapacitet: efter ? `${api.h1(efter.obemannatKundbehovH)} h` : "–",
    vikarie: fe?.vikarie ? `${fe.vikarie.antalBehalls} pass att tillsätta` : "–",
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Granska</div>
        <h2 className="mt-1 text-3xl font-extrabold text-deep">Resultat av bemanningsbalansen</h2>
        <p className="mt-2 max-w-2xl text-base text-muted-foreground">{vcStatusText(summary?.status)}</p>
        <p className="mt-1 text-sm font-semibold text-deep">{berakningsKallaText(api.berakningsKalla())}</p>
      </div>
      <TreOmraden
        summary={
          summary
            ? {
                ...summary,
                coveragePercent: summary.coveragePercent ?? efter?.tackningPct ?? null,
                customerNearPercent: summary.customerNearPercent ?? efter?.kundnaraPct ?? null,
              }
            : {
                status: "FEASIBLE",
                coveragePercent: efter?.tackningPct ?? null,
                customerNearPercent: efter?.kundnaraPct ?? null,
                cost: Math.round((efter?.kostnad || 0) * 100),
                hardViolations: [],
                warnings: (fe?.varningar || []).map((m) => ({ message: m })),
                changedShiftCount: api.schemaForandringar().length,
                lockedShiftCount: api.schemaPass().filter((p) => p.last).length,
                explanationSummary: summary?.explanationSummary || "",
                performanceSummary: "",
              }
        }
        hardCount={api.regelbrott()}
        locked={api.schemaPass().filter((p) => p.last).length}
        resurs={resurs}
      />
      <Card className="rounded-2xl p-6 shadow-lift">
        <h3 className="text-lg font-extrabold text-deep">Förändringar</h3>
        <ul className="mt-3 space-y-1 text-sm text-deep">
          <li>Ändrade pass: {summary?.changedShiftCount ?? api.schemaForandringar().length}</li>
          <li>Låsta pass: {summary?.lockedShiftCount ?? api.schemaPass().filter((p) => p.last).length}</li>
        </ul>
        {summary?.explanationSummary ? (
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{summary.explanationSummary}</p>
        ) : null}
        <div className="mt-5 flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => api.setTab("schemaforslag")}>
            Godkänn och öppna schema <ArrowRight />
          </Button>
        </div>
      </Card>
      <ForeEfter {...props} />
    </div>
  );
}
