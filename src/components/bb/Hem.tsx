import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { VyProps } from "@/lib/bb/vy";
import { ProcessFlode } from "./ProcessFlode";
import { TreOmraden } from "./TreOmraden";
import { Uppladdning } from "./Uppladdning";
import {
  kostnadPerTacktKundtimme,
  lasMotorSummary,
  processStegLagen,
  skapaBalansHinder,
} from "@/lib/bb/vcFlode";
import { fmtH, fmtPct } from "@/lib/bb/vy";

export function Hem(props: VyProps) {
  const { api } = props;
  if (!api.underlag().godkand.allt && !api.underlag().godkand.kund) {
    return <Uppladdning {...props} />;
  }

  const hinder = skapaBalansHinder({
    kundGodkand: api.underlag().godkand.kund,
    medarbetare: api.medarbetare(),
    harUnderlag: api.harUnderlag() || api.underlag().godkand.kund,
  });
  const summary = lasMotorSummary(api.motorResultat());
  const fe = api.foreEfter();
  const lage = fe?.efter ?? api.foreLage();
  const steg = processStegLagen({
    aktivTab: "hem",
    kundGodkand: api.underlag().godkand.kund,
    medarbetareOk: !hinder.skal.some((s) => s.includes("arbetstidsmodell")),
    harResultat: api.harBalans(),
    harVarning: api.regelbrott() > 0,
    blockeradSkapa: !hinder.aktiv,
  });

  const aktiva = api.medarbetare().filter((m) => !m.vakant);
  const ssg =
    aktiva.length > 0
      ? `${Math.round(aktiva.reduce((s, m) => s + Number(m.grad || 0), 0) / aktiva.length)} %`
      : "–";
  const perTackt =
    lage && lage.bemannatKundbehovH > 0 ? kostnadPerTacktKundtimme(lage.kostnad, lage.bemannatKundbehovH) : null;
  const resurs = lage
    ? {
        intakt: api.kr(lage.intakt),
        schemakostnad: api.kr(lage.kostnad),
        marginal: api.kr(lage.resultat),
        overkapacitet: `${fmtH(lage.overkapacitetH)}`,
        underkapacitet: `${fmtH(lage.obemannatKundbehovH)}`,
        vakanta: api.underlag().schema ? `${api.underlag().schema?.vakanta} vakanta rader` : "–",
        ssg,
        overtids: "–",
        vikarie: api.underlag().schema ? `${api.underlag().schema?.vikarier} vikarier` : "–",
        korttids: "–",
        kostnadPerTackt: perTackt != null ? api.kr(perTackt) : "–",
      }
    : undefined;

  const mapped = summary
    ? {
        ...summary,
        coveragePercent: summary.coveragePercent ?? lage?.tackningPct ?? null,
        customerNearPercent: summary.customerNearPercent ?? lage?.kundnaraPct ?? null,
      }
    : lage
      ? {
          status: api.harBalans() ? "FEASIBLE" : "NOT_RUN",
          coveragePercent: lage.tackningPct,
          customerNearPercent: lage.kundnaraPct,
          cost: Math.round(lage.kostnad * 100),
          hardViolations: [],
          warnings: [],
          changedShiftCount: 0,
          lockedShiftCount: 0,
          explanationSummary: "",
          performanceSummary: "",
        }
      : null;

  return (
    <div className="space-y-8">
      <div>
        <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Översikt</div>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-deep sm:text-4xl">Bemanningsbalans</h1>
        <p className="mt-2 max-w-2xl text-base leading-relaxed text-muted-foreground">
          Kundbehov, medarbetare, förslag, granskning och uppföljning – i den ordningen.
        </p>
      </div>

      <ProcessFlode steg={steg} onValj={(id) => api.setTab(id)} />

      <TreOmraden
        summary={mapped}
        hardCount={api.regelbrott()}
        locked={api.schemaPass().filter((p) => p.last).length}
        resurs={resurs}
        tom={!lage && !summary}
      />

      <Card className="rounded-2xl p-6 shadow-lift">
        <h2 className="text-xl font-extrabold text-deep">Nästa steg</h2>
        <Button
          className="mt-4"
          size="lg"
          disabled={!hinder.aktiv}
          aria-disabled={!hinder.aktiv}
          title={hinder.aktiv ? undefined : hinder.skal.join(". ")}
          onClick={() => api.setTab("motor")}
        >
          <Sparkles /> Skapa bemanningsbalans
        </Button>
        {!hinder.aktiv ? (
          <ul className="mt-3 space-y-1 text-sm text-warning" aria-live="polite">
            {hinder.skal.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">Underlaget räcker för att räkna ett förslag.</p>
        )}
        {lage ? (
          <p className="mt-4 text-xs text-muted-foreground">
            Täckt behov {fmtPct(lage.tackningPct)} · kundnära {fmtPct(lage.kundnaraPct)} – två skilda mått.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
