import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { VyProps } from "@/lib/bb/vy";

const DOLDA = new Set(["kontaktpersonstid", "samverkan_kund"]);

/** Planeringssteg i huvudflödet. Ändrar inte aktivitetskatalogen. */
export function Planering({ api }: VyProps) {
  const aktiviteter = api.planAktiviteter().filter((a) => !DOLDA.has(a.id) && !DOLDA.has(a.aktivitetstyp));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-[14px] font-semibold tracking-[0.14em] text-primary uppercase">Planering</p>
        <h2 className="mt-2 text-[32px] font-extrabold tracking-tight text-deep">Planeringsaktiviteter</h2>
        <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
          Välj de aktiviteter som ska ingå i perioden. Kontaktpersonstid och Samverkan kring kund visas inte här.
        </p>
      </div>

      <Card className="rounded-[28px] p-8 shadow-lift">
        <ul className="space-y-3">
          {aktiviteter.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-3 border-b border-border/60 py-3 last:border-0">
              <input
                type="checkbox"
                checked={a.aktiv}
                onChange={(e) => api.setPlanAktivitet(a.id, "aktiv", e.currentTarget.checked)}
                aria-label={a.namn}
              />
              <span className="flex-1 text-[16px] font-semibold text-deep">{a.namn}</span>
              {a.aktiv ? (
                <>
                  <input
                    className="h-9 w-16 rounded-lg border border-input px-2 text-sm tabular-nums"
                    value={String(a.omfattning)}
                    onChange={(e) => api.setPlanAktivitet(a.id, "omfattning", Number(e.currentTarget.value) || 0)}
                    aria-label={`Omfattning ${a.namn}`}
                  />
                  <span className="text-sm text-muted-foreground">{a.enhet === "timmar" ? "h" : "min"}</span>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>

      <Button className="h-14 rounded-2xl px-8 text-[16px]" size="lg" onClick={() => api.setTab("forutsattningar")}>
        Spara och fortsätt <ArrowRight />
      </Button>
    </div>
  );
}
