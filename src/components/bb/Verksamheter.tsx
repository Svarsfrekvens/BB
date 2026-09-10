import { useSyncExternalStore, useState } from "react";
import { Plus, X, Building2 } from "lucide-react";
import { bbVy } from "@/lib/bb/vy";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BekraftaDialog } from "./Bekrafta";
import { notera } from "@/lib/bb/notis";

/** Verksamhetsväxlare: upp till fyra verksamheter, en aktiv i taget. */
export function Verksamheter() {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  const [taBort, setTaBort] = useState<{ id: string; org: string } | null>(null);
  const api = v.api;
  if (!api || !v.verks.length) return null;
  const kanLagga = v.verks.length < v.maxVerks;


  return (
    <div className="mb-5 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card p-2.5 shadow-sm">
      <span className="ml-1.5 flex items-center gap-1.5 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
        <Building2 className="size-3.5" /> Verksamhet
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        {v.verks.map((verk) => {
          const aktiv = verk.id === v.aktivVerks;
          return (
            <span
              key={verk.id}
              className={cn(
                "group flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm font-semibold transition-all duration-200",
                aktiv
                  ? "border-primary bg-primary-soft text-primary"
                  : "border-border bg-background text-deep hover:bg-muted",
              )}
            >
              <button type="button" className="flex items-center gap-2" onClick={() => api.setActiveVerks(verk.id)}>
                <span
                  className={cn("size-2 rounded-full", verk.filled ? "bg-[var(--success)]" : "bg-muted-foreground/40")}
                  aria-hidden="true"
                />
                {verk.org}
              </button>
              {v.verks.length > 1 && (
                <button
                  type="button"
                  aria-label={`Ta bort ${verk.org}`}
                  className="grid size-5 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-primary"
                  onClick={() => setTaBort({ id: verk.id, org: verk.org })}
                >
                  <X className="size-3" />
                </button>
              )}
            </span>
          );
        })}
      </div>
      {kanLagga ? (
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => api.addVerks()}>
          <Plus /> Lägg till verksamhet
        </Button>
      ) : (
        <span className="ml-auto text-[11px] text-muted-foreground">Max {v.maxVerks} verksamheter</span>
      )}

      <BekraftaDialog
        open={!!taBort}
        onOpenChange={(o) => { if (!o) setTaBort(null); }}
        rubrik={`Ta bort ${taBort?.org ?? ""}?`}
        text="Verksamheten och dess inlästa data tas bort. Det går inte att ångra."
        onBekrafta={() => {
          const namn = taBort?.org ?? "";
          if (taBort) api.taBortVerks(taBort.id);
          setTaBort(null);
          notera(`${namn} borttagen`, "ok");
        }}
      />
    </div>
  );
}
