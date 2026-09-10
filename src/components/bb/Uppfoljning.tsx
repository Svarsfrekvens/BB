import { Clock, Coins, Hourglass, Target, TrendingUp, Upload, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { VyProps } from "@/lib/bb/vy";
import { TomtLage } from "./Tomt";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

/** Uppföljning: planerade värden nu, faktiskt utfall när perioden är slut. */
export function Uppfoljning({ api }: VyProps) {
  const m = api.foreEfter();
  const plan = m ? (m.efter ?? m.fore) : api.foreLage();

  if (!plan) {
    return (
      <TomtLage
        ikon={TrendingUp}
        rubrik="Uppföljningen väntar på ett planerat schema"
        text="Läs in kundernas behov och schemat och skapa bemanningsbalansen. Då visas det planerade läget här, och när perioden är slut kan det faktiska utfallet läggas in."
        atgarder={[{ text: "Gå till Underlag", onClick: () => api.setTab("uppladdning"), ikon: Upload }]}
      />
    );
  }

  const rader = [
    { l: "Kundnära tid", Ic: Target, plan: `${plan.kundnaraPct.toFixed(1)} %`.replace(".", ",") },
    { l: "Planerade personaltimmar", Ic: Clock, plan: api.h1(plan.schematidH) },
    { l: "Personalkostnad", Ic: Coins, plan: api.kr(plan.kostnad), faktiskt: "Utfall kräver tidrapport" },
    { l: "Underbemannade timmar", Ic: Users, plan: api.h1(plan.obemannatH) },
    { l: "Överbemannade timmar", Ic: Users, plan: api.h1(plan.overkapacitetH) },
    { l: "Ekonomiskt resultat", Ic: Coins, plan: api.kr(plan.resultat) },
  ] as { l: string; Ic: typeof Target; plan: string; faktiskt?: string }[];

  const u = api.utfall();
  const nr = (x: number | null, enhet: string) => (x == null ? "–" : `${x.toFixed(1).replace(".", ",")} ${enhet}`);

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <Eyebrow>Uppföljning</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Planerat mot faktiskt utfall</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Här står det planerade läget för perioden. Det faktiska utfallet fylls i när perioden är slut och nya
              filer läses in – appen hittar inte på några siffror i förväg.
            </p>
          </div>
          <Badge className="rounded-full bg-muted px-4 py-1.5 text-xs font-bold text-muted-foreground">
            <Hourglass className="size-3" /> Väntar på utfall
          </Badge>
        </div>
      </Card>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                <th className="px-6 py-3 text-left">Mått</th>
                <th className="px-6 py-3 text-right">Planerat</th>
                <th className="px-6 py-3 text-right">Faktiskt</th>
                <th className="px-6 py-3 text-right">Skillnad</th>
              </tr>
            </thead>
            <tbody>
              {rader.map((r) => (
                <tr key={r.l} className="border-t border-border">
                  <th className="border-t border-border px-6 py-3 text-left text-sm font-bold text-deep">
                    <span className="inline-flex items-center gap-2">
                      <r.Ic className="size-4 text-primary" /> {r.l}
                    </span>
                  </th>
                  <td className="border-t border-border px-6 py-3 text-right font-bold tabular-nums text-deep">
                    {r.plan}
                  </td>
                  <td className="border-t border-border px-6 py-3 text-right text-muted-foreground">{r.faktiskt ?? "Väntar på utfall"}</td>
                  <td className="border-t border-border px-6 py-3 text-right text-muted-foreground">—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {u ? (
        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <Eyebrow>Ur kundfilen</Eyebrow>
          <h3 className="mt-1 text-lg font-extrabold text-deep">Så gick insatserna</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Statusfälten kommer direkt ur Sekoia-exporten – inget är uppskattat.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { l: "Utförda", v: `${u.utford} av ${u.antal}` },
              { l: "Inställda", v: String(u.installd) },
              { l: "Flyttade", v: String(u.flyttad) },
              { l: "Ej utförda", v: String(u.ejUtford) },
              { l: "Inom sitt tidsfönster", v: u.inomFonsterPct == null ? "Saknar Utförd kl." : nr(u.inomFonsterPct, "%") },
              { l: "Snittavvikelse mot planerad tid", v: u.snittAvvikelseMin == null ? "Saknar Utförd kl." : nr(u.snittAvvikelseMin, "min") },
              { l: "Insatser med registrerad tid", v: String(u.medUtford) },
            ].map((k) => (
              <div key={k.l} className="rounded-2xl border border-border bg-card px-4 py-3 shadow-sm">
                <span className="block text-xs font-semibold text-muted-foreground">{k.l}</span>
                <strong className="mt-1 block text-xl font-extrabold tabular-nums text-deep">{k.v}</strong>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card className="gap-0 rounded-2xl bg-muted/50 p-6 shadow-lift">
        <p className="text-sm leading-relaxed text-muted-foreground">
          När perioden är slut läser du in det utförda schemat och den nya kundfilen. Då jämförs planerat mot faktiskt i
          samma tabell.
        </p>
      </Card>
    </div>
  );
}
