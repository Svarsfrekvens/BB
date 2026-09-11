import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { VyProps } from "@/lib/bb/vy";
import { TreOmraden } from "./TreOmraden";
import { Uppladdning } from "./Uppladdning";
import {
  KAPACITET_FORKLARING,
  KUNDNARA_FORKLARING,
  TACKT_BEHOV_FORKLARING,
  berakningsKallaText,
  genomsnittligSsgPct,
  kostnadPerTacktKundtimme,
  lasMotorSummary,
  readinessFranApi,
  ssgUtnyttjandePct,
  timmarEllerTomt,
} from "@/lib/bb/vcFlode";
import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { fmtPct } from "@/lib/bb/vy";

export function Hem(props: VyProps) {
  const { api, state } = props;
  if (!api.underlag().godkand.kund) {
    return <Uppladdning {...props} />;
  }

  const readiness = readinessFranApi(api);
  const summary = lasMotorSummary(api.motorResultat());
  const fe = api.foreEfter();
  const lage = fe?.efter ?? api.foreLage();
  const ssgSnitt = genomsnittligSsgPct(api.medarbetare());
  const ssgUtnytt = ssgUtnyttjandePct(null, null);
  const perTackt =
    lage && lage.bemannatKundbehovH > 0 ? kostnadPerTacktKundtimme(lage.kostnad, lage.bemannatKundbehovH) : null;
  const vakanta = timmarEllerTomt(null);
  const vikarie = timmarEllerTomt(null);
  const resurs = lage
    ? {
        intakt: api.kr(lage.intakt),
        schemakostnad: api.kr(lage.kostnad),
        marginal: api.kr(lage.resultat),
        overkapacitet: `${api.h1(lage.overkapacitetH)} h`,
        underkapacitet: `${api.h1(lage.obemannatKundbehovH)} h`,
        vakanta: vakanta.text,
        vakantaSaknas: vakanta.saknas,
        genomsnittligSsg: ssgSnitt != null ? `${Math.round(ssgSnitt)} %` : "–",
        ssgUtnyttjande: ssgUtnytt == null ? undefined : `${ssgUtnytt.toFixed(1)} %`,
        vikarie: vikarie.text,
        vikarieSaknas: vikarie.saknas,
        kostnadPerTackt: perTackt != null ? api.kr(perTackt) : "–",
      }
    : {
        genomsnittligSsg: ssgSnitt != null ? `${Math.round(ssgSnitt)} %` : undefined,
      };

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
        {api.harBalans() ? (
          <p className="mt-2 text-sm font-semibold text-deep">{berakningsKallaText(api.berakningsKalla())}</p>
        ) : null}
      </div>

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
          data-cta="skapa-bemanningsbalans"
          disabled={!readiness.ready}
          aria-disabled={!readiness.ready}
          title={readiness.ready ? undefined : readiness.blockingReasons.join(". ")}
          onClick={() => void korBemanningsbalans({ api, state })}
        >
          <Sparkles /> Skapa bemanningsbalans
        </Button>
        {!readiness.ready ? (
          <ul className="mt-3 space-y-1 text-sm text-warning" aria-live="polite">
            {readiness.blockingReasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">Underlaget räcker för att räkna ett förslag.</p>
        )}
        <p className="mt-4 text-xs text-muted-foreground" title={TACKT_BEHOV_FORKLARING}>
          {TACKT_BEHOV_FORKLARING}
        </p>
        <p className="mt-1 text-xs text-muted-foreground" title={KUNDNARA_FORKLARING}>
          {KUNDNARA_FORKLARING}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{KAPACITET_FORKLARING}</p>
        {lage ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Täckt behov {fmtPct(lage.tackningPct)} · kundnära {fmtPct(lage.kundnaraPct)} – två skilda mått.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
