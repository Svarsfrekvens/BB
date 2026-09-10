import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

export function PerKund({ d, state, api }: VyProps) {
  if (!d) return null;
  const h1 = api.h1;
  const kunder = d.kunder;

  return (
    <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
      <div className="flex flex-wrap items-start justify-between gap-4 px-6 pt-6 pb-5 md:px-8">
        <div className="flex gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-deep">
            <Users className="size-5" />
          </span>
          <div>
            <Eyebrow>Per kund</Eyebrow>
            <h1 className="mt-0.5 text-2xl font-extrabold tracking-tight text-deep">Samlat kundbehov</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Matchning sker på kundnamnet, aldrig via sortering. Gemensamma insatser redovisas separat och ingår i
              totalen.
            </p>
          </div>
        </div>
        <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
          {kunder.length} kunder
        </Badge>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-border/60 bg-muted/40 text-left">
              <th className="px-6 py-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Kund</th>
              <th className="px-6 py-3 text-right text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                Insatser
              </th>
              <th className="px-6 py-3 text-right text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                Kundbehov
              </th>
              <th className="px-6 py-3 text-right text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                Personalbehov inkl. dubbel
              </th>
              <th className="px-6 py-3 text-right text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                Snitt/vecka
              </th>
            </tr>
          </thead>
          <tbody>
            {kunder.map((k) => (
              <tr key={k.kund} className="border-b border-border/50 transition-colors hover:bg-muted/40">
                <td className="px-6 py-3 font-semibold text-deep">{k.kund}</td>
                <td className="px-6 py-3 text-right text-muted-foreground tabular-nums">{k.insatser}</td>
                <td className="px-6 py-3 text-right font-bold text-deep tabular-nums">{h1(k.kundbehovH)} h</td>
                <td className="px-6 py-3 text-right text-deep tabular-nums">{h1(k.personalbehovH ?? 0)} h</td>
                <td className="px-6 py-3 text-right text-muted-foreground tabular-nums">
                  {h1((k.kundbehovH / state.analysisDays) * 7)} h
                </td>
              </tr>
            ))}
            <tr className="border-t-2 border-border bg-muted/40">
              <td className="px-6 py-4 font-extrabold text-deep">Totalt</td>
              <td className="px-6 py-4 text-right font-extrabold text-deep tabular-nums">{d.n.antalInsatser}</td>
              <td className="px-6 py-4 text-right font-extrabold text-deep tabular-nums">{h1(d.n.kundbehovH)} h</td>
              <td className="px-6 py-4 text-right font-extrabold text-deep tabular-nums">{h1(d.n.personalbehovH)} h</td>
              <td />
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}
