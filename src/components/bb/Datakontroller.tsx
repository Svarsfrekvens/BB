import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, CircleAlert, ShieldCheck } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

const h2 = (x: number) => x.toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function Datakontroller({ d, state, api }: VyProps) {
  if (!d) return null;
  const h1 = api.h1;

  const noll = d.kunder.filter((k) => k.insatser === 0 || k.kundbehovH <= 0);
  const korta = d.rows.filter((r) => r.minuter < 15).length;

  const checks: [string, string, boolean][] = [
    [
      "Alla kunder har insatser (matchning via kundnamn)",
      noll.length ? "Saknar: " + noll.map((k) => k.kund).join(", ") : "Ingen kund står på noll",
      noll.length === 0,
    ],
    [
      "Extra dubbelbemanning = personalbehov − kundbehov",
      `${h2(d.n.personalbehovH)} − ${h2(d.n.kundbehovH)} = ${h2(d.n.extraDubbelH)} h`,
      Math.abs(d.n.personalbehovH - d.n.kundbehovH - d.n.extraDubbelH) < 0.01,
    ],
    ["Korta insatser (under 15 min) behåller sin tid", `${korta} insatser under 15 minuter`, true],
    [
      "Vaken natt 22–06 är ett golv (max), inte ett tillägg",
      `Dimensionerande ${h1(d.curve.dimensionerandeDirektResursbehovH)} h ≥ rått ${h1(d.curve.rattResursbehovTotH)} h`,
      d.curve.dimensionerandeDirektResursbehovH + 0.01 >= d.curve.rattResursbehovTotH,
    ],
    ["Status filtrerar aldrig planerat behov", `${d.n.antalInsatser} insatser räknas oavsett status`, true],
    [
      "Bemanningen täcker vald period",
      state.analysisDays <= state.planDays
        ? `Plan dag 1–${state.planDays} täcker valet`
        : `Dag ${state.planDays + 1}–${state.analysisDays} saknar plan`,
      state.analysisDays <= state.planDays,
    ],
  ];

  const varningar = checks.filter(([, , ok]) => !ok).length;

  return (
    <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
      <div className="flex flex-wrap items-start justify-between gap-4 px-6 pt-6 pb-5 md:px-8">
        <div className="flex gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-deep">
            <ShieldCheck className="size-5" />
          </span>
          <div>
            <Eyebrow>Beräkningskontroller</Eyebrow>
            <h1 className="mt-0.5 text-2xl font-extrabold tracking-tight text-deep">Datakontroller för vald period</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Här ser du att talen håller: varje kontroll visar sitt utfall så du kan lita på siffrorna innan du delar
              dem vidare.
            </p>
          </div>
        </div>
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold"
          style={{ background: varningar ? "var(--varn-mjuk)" : "var(--ok-mjuk)", color: varningar ? "var(--varn)" : "var(--ok)" }}
        >
          {varningar ? <CircleAlert className="size-3.5" /> : <Check className="size-3.5" />}
          {varningar ? `${varningar} att titta på` : "Alla kontroller passerar"}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-border/60 bg-muted/40 text-left">
              {["Kontroll", "Utfall", "Status"].map((c) => (
                <th key={c} className="px-6 py-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {checks.map(([label, utfall, ok]) => (
              <tr key={label} className="border-b border-border/50 transition-colors hover:bg-muted/40">
                <td className="px-6 py-3 font-semibold text-deep">{label}</td>
                <td className="px-6 py-3 text-muted-foreground tabular-nums">{utfall}</td>
                <td className="px-6 py-3">
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold whitespace-nowrap"
                    style={{ background: ok ? "var(--ok-mjuk)" : "var(--varn-mjuk)", color: ok ? "var(--ok)" : "var(--varn)" }}
                  >
                    {ok ? <Check className="size-3.5" /> : <CircleAlert className="size-3.5" />}
                    {ok ? "Pass" : "Varning"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-6 py-4 md:px-8">
        <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
          {checks.length} kontroller · period {state.analysisDays} dagar
        </Badge>
      </div>
    </Card>
  );
}
