import { useSyncExternalStore } from "react";
import { ArrowRight, Building2, Info } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { bbVy } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

/** Steg 1: välj vilken verksamhet du arbetar med. */
export function Verksamhet({ api }: VyProps) {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  const aktiv = v.verks.find((x) => x.id === v.aktivVerks);

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Steg 1 · Verksamhet</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Välj verksamhet</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Börja med att välja vilken verksamhet du vill arbeta med. Varje verksamhet har egen kundgrupp, eget schema och
          egna medarbetaruppgifter.
        </p>
      </Card>

      <Card className="max-w-xl gap-0 rounded-2xl p-7 shadow-lift">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Eyebrow>Verksamhet</Eyebrow>
            <h3 className="mt-1 text-lg font-extrabold text-deep">Vilken enhet arbetar du med?</h3>
          </div>
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-teal-soft text-teal">
            <Building2 className="size-5" />
          </span>
        </div>

        <select
          value={v.aktivVerks}
          onChange={(e) => api.setActiveVerks(e.target.value)}
          className="mt-4 h-12 w-full rounded-xl border border-input bg-card px-3 text-base font-semibold text-deep outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          {v.verks.map((verk) => (
            <option key={verk.id} value={verk.id}>
              {verk.org}
            </option>
          ))}
        </select>

        <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-blue-soft px-4 py-3 text-sm text-deep">
          <Info className="mt-0.5 size-4 shrink-0 text-blue" />
          <span>
            Vald verksamhet: <strong className="font-bold">{aktiv?.org || "–"}</strong>. Gå vidare till Kundgrupp för att
            ladda upp underlag.
          </span>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Button onClick={() => api.setTab("kundgrupp")}>
            Fortsätt till Kundgrupp <ArrowRight />
          </Button>
          {v.verks.length < v.maxVerks ? (
            <Button variant="outline" onClick={() => api.addVerks()}>
              Lägg till verksamhet
            </Button>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
