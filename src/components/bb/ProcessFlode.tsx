import { Check, AlertTriangle, Ban, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessStegLage } from "@/lib/bb/vcFlode";

const LAGE: Record<ProcessStegLage, { text: string; klass: string }> = {
  ej: { text: "Ej påbörjad", klass: "border-border bg-card text-muted-foreground" },
  pa: { text: "Pågående", klass: "border-primary bg-primary text-primary-foreground shadow-lift" },
  klar: { text: "Klar", klass: "border-[#004691]/20 bg-[#CCD6EA] text-[#004691]" },
  varning: { text: "Varning", klass: "border-warning/40 bg-warning-soft text-warning" },
  blockerad: { text: "Blockerad", klass: "border-destructive/30 bg-danger-soft text-destructive" },
};

export function ProcessFlode({
  steg,
  onValj,
}: {
  steg: { id: string; label: string; lage: ProcessStegLage; typ?: "lage" | "handling" }[];
  onValj?: (id: string) => void;
}) {
  const lagen = steg.filter((s) => s.typ !== "handling");
  const handlingar = steg.filter((s) => s.typ === "handling");
  return (
    <nav
      aria-label="Före → Balans → Utfall"
      data-process-flode="skal"
      data-tidslinje="Före → Balans → Utfall"
      className="space-y-2"
    >
      <div className="flex flex-wrap items-center gap-x-1 gap-y-3">
        {lagen.map((s, i) => {
          const vis = LAGE[s.lage];
          return (
            <div key={s.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onValj?.(s.id)}
                data-steg-typ="lage"
                aria-current={s.lage === "pa" ? "step" : undefined}
                aria-label={`${s.label}: ${vis.text}`}
                className={cn(
                  "flex items-center gap-2 rounded-2xl border px-3 py-2 text-left text-sm font-semibold transition-colors",
                  vis.klass,
                )}
              >
                <span className="grid size-6 place-items-center rounded-full bg-white/30" aria-hidden>
                  {s.lage === "klar" ? (
                    <Check className="size-3.5" />
                  ) : s.lage === "varning" ? (
                    <AlertTriangle className="size-3.5" />
                  ) : s.lage === "blockerad" ? (
                    <Ban className="size-3.5" />
                  ) : (
                    <Circle className="size-3.5" />
                  )}
                </span>
                <span>
                  <span className="block leading-tight">{s.label}</span>
                  <span className="block text-[11px] font-medium opacity-80">{vis.text}</span>
                </span>
              </button>
              {i < lagen.length - 1 ? (
                <span className="hidden px-1 text-lg font-light text-[#004691]/40 sm:inline" aria-hidden>
                  →
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
      {handlingar.length ? (
        <div className="flex flex-wrap items-center gap-2" data-handlingar="inom-tidslinje">
          {handlingar.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onValj?.(s.id)}
              data-steg-typ="handling"
              aria-label={`Handling ${s.label}: ${LAGE[s.lage].text}`}
              className="rounded-md px-2 py-1 text-xs font-semibold text-muted-foreground underline-offset-2 hover:text-deep hover:underline"
            >
              {s.label}
            </button>
          ))}
        </div>
      ) : null}
    </nav>
  );
}
