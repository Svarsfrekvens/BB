import { Check, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { balansUtfallText, fasSteg, type SparatMotorJobb } from "@/lib/bb/motorJobb";

export function BalansPagar({ job }: { job: SparatMotorJobb | null | undefined }) {
  if (!job?.id) return null;
  const klar = job.phase === "completed" || job.phase === "failed";
  const steg = fasSteg(job.phase, job.phaseText);
  const titel = klar ? balansUtfallText(job.outcome) || "Balans klar" : "Bemanningsbalans skapas";
  return (
    <Card className="rounded-2xl p-6 shadow-lift" data-balans-jobb={job.phase || "queued"}>
      <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Beräkning</div>
      <h2 className="mt-1 text-xl font-extrabold text-deep">{titel}</h2>
      <ol className="mt-4 space-y-2 text-sm text-deep">
        {steg.map((s) => (
          <li key={s.id} className="flex items-start gap-2">
            {s.klar ? (
              <Check className="mt-0.5 size-4 shrink-0 text-success" />
            ) : s.pa ? (
              <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-primary" />
            ) : (
              <span className="mt-0.5 inline-block size-4 shrink-0 rounded-full border border-border" />
            )}
            <span className={s.klar || s.pa ? "font-semibold" : "text-muted-foreground"}>{s.label}</span>
          </li>
        ))}
      </ol>
      {job.phase === "solving" ? (
        <p className="mt-3 text-sm text-muted-foreground">BB söker fortfarande efter en bättre lösning.</p>
      ) : null}
      {job.stale ? (
        <p className="mt-3 text-sm font-semibold text-warning">
          Balansen bygger på ett tidigare underlag – skapa om Balans.
        </p>
      ) : null}
      {!klar ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Du kan fortsätta arbeta i BB. Vi visar resultatet här när det är klart.
        </p>
      ) : null}
    </Card>
  );
}
