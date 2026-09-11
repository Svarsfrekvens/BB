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
  steg: { id: string; label: string; lage: ProcessStegLage }[];
  onValj?: (id: string) => void;
}) {
  return (
    <nav aria-label="Processflöde" data-process-flode="skal" className="flex flex-wrap items-center gap-x-1 gap-y-3">
      {steg.map((s, i) => {
        const vis = LAGE[s.lage];
        return (
          <div key={s.id} className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onValj?.(s.id)}
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
            {i < steg.length - 1 ? (
              <span className="hidden px-1 text-lg font-light text-[#004691]/40 sm:inline" aria-hidden>
                →
              </span>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}
