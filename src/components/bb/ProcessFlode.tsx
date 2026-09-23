import { Check, AlertTriangle, Ban, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessStegLage } from "@/lib/bb/vcFlode";

const LAGE: Record<ProcessStegLage, { text: string; klass: string }> = {
  ej: { text: "Ej påbörjad", klass: "border-transparent bg-white/90 text-[#5a6272] shadow-[0_4px_14px_rgba(16,32,72,0.04)]" },
  pa: {
    text: "Pågående",
    klass:
      "z-20 -translate-y-[7px] scale-[1.07] border-transparent bg-gradient-to-br from-deep via-[#0b3a7a] to-[#163a73] px-5 py-4 text-white shadow-[0_18px_36px_rgba(0,40,105,0.28)] motion-reduce:translate-y-0 motion-reduce:scale-100",
  },
  klar: { text: "Klar", klass: "border-transparent bg-primary-soft/80 text-deep" },
  varning: { text: "Varning", klass: "border-warning/40 bg-warning-soft text-warning" },
  blockerad: { text: "Blockerad", klass: "border-destructive/30 bg-danger-soft text-destructive" },
};

function kortNamn(label: string, aktiv: boolean) {
  if (aktiv) return label;
  if (label === "Medarbetare & villkor") return "Medarbetare";
  if (label === "Skapa balans") return "Skapa";
  return label;
}

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
      aria-label="Process"
      data-process-flode="oversikt"
      data-tidslinje="Före → Balans → Utfall"
      className="overflow-x-auto pb-3 pt-3"
    >
      <ol className="flex min-w-max items-end gap-0 px-1">
        {lagen.map((s, i) => {
          const vis = LAGE[s.lage];
          const aktiv = s.lage === "pa";
          const klar = s.lage === "klar";
          const nastaAktiv = lagen[i + 1]?.lage === "pa";
          return (
            <li key={s.id} className="flex items-end">
              <button
                type="button"
                onClick={() => onValj?.(s.id)}
                data-steg-typ="lage"
                aria-current={aktiv ? "step" : undefined}
                aria-label={`${s.label}: ${vis.text}`}
                className={cn(
                  "bb-process-steg flex items-center gap-2.5 rounded-[22px] border px-3 py-2.5 text-left transition-[transform,box-shadow,background-color,color,padding] duration-200 ease-out motion-reduce:transition-none",
                  vis.klass,
                  !aktiv && "hover:-translate-y-0.5",
                )}
              >
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-full text-[13px] font-bold",
                    aktiv ? "bg-white/20 text-white" : klar ? "bg-white text-deep" : "bg-[#eef0f6] text-muted-foreground",
                  )}
                  aria-hidden
                >
                  {klar ? (
                    <Check className="size-4" />
                  ) : s.lage === "varning" ? (
                    <AlertTriangle className="size-3.5" />
                  ) : s.lage === "blockerad" ? (
                    <Ban className="size-3.5" />
                  ) : s.lage === "ej" ? (
                    <span>{i + 1}</span>
                  ) : (
                    <Circle className="size-3.5 fill-current" />
                  )}
                </span>
                <span>
                  <span className={cn("block leading-snug", aktiv ? "text-[16px] font-extrabold" : "text-[14px] font-semibold")}>
                    {kortNamn(s.label, aktiv)}
                  </span>
                  <span className="sr-only">{vis.text}</span>
                </span>
              </button>
              {i < lagen.length - 1 ? (
                <span
                  className={cn(
                    "mb-3 mx-1 text-[20px] font-light leading-none text-deep/25 transition-colors duration-200 motion-reduce:transition-none",
                    (aktiv || nastaAktiv || klar) && "text-deep/50",
                  )}
                  aria-hidden
                >
                  →
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      {handlingar.length ? (
        <div className="mt-2 flex flex-wrap items-center gap-2" data-handlingar="inom-tidslinje">
          {handlingar.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onValj?.(s.id)}
              data-steg-typ="handling"
              aria-label={`Handling ${s.label}: ${LAGE[s.lage].text}`}
              className="rounded-md px-2 py-1 text-sm font-semibold text-muted-foreground underline-offset-2 hover:text-deep hover:underline"
            >
              {s.label}
            </button>
          ))}
        </div>
      ) : (
        <div className="sr-only" data-handlingar="inom-tidslinje" />
      )}
    </nav>
  );
}
