import { Sparkles, ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { VyProps } from "@/lib/bb/vy";
import { TreOmraden } from "./TreOmraden";
import { Uppladdning } from "./Uppladdning";
import {
  KAPACITET_FORKLARING,
  KUNDNARA_FORKLARING,
  TACKT_BEHOV_FORKLARING,
  balansKanGodkannas,
  raknaSaknadeKompetenskrav,
  genomsnittligSsgPct,
  getTidslage,
  hemHuvudCta,
  hemStatusText,
  lasMotorSummary,
  readinessFranApi,
  ssgUtnyttjandePct,
  tidslageText,
  timmarEllerTomt,
  visningsNamnVerksamhet,
} from "@/lib/bb/vcFlode";
import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { fmtH } from "@/lib/bb/vy";

export function Hem(props: VyProps) {
  const { api, state } = props;
  if (!api.underlag().godkand.kund) {
    return <Uppladdning {...props} />;
  }

  const readiness = readinessFranApi(api);
  const summary = lasMotorSummary(api.motorResultat());
  const fe = api.foreEfter();
  const harBalans = api.harBalans();
  const lageId = getTidslage({ harBalans, harUtfall: false });
  const lageInfo = tidslageText(lageId);
  const lage = harBalans ? fe?.efter ?? api.foreLage() : api.foreLage() ?? fe?.fore;
  const hard = api.regelbrott();
  const godkannbar = balansKanGodkannas({
    tacktBehovPct: harBalans ? lage?.tackningPct : null,
    hardViolations: harBalans ? hard : 0,
    saknadeKompetenskrav: harBalans
      ? raknaSaknadeKompetenskrav([...(summary?.hardViolations || []), ...(summary?.warnings || [])])
      : 0,
  });
  const balansGodkand = Boolean(state && (state as { balansGodkand?: boolean }).balansGodkand);
  const cta = hemHuvudCta({ lage: lageId, ready: readiness.ready, godkannbar: godkannbar.ok, balansGodkand });
  const status = hemStatusText({
    lage: lageId,
    ready: readiness.ready,
    blockingReasons: readiness.blockingReasons,
    godkannbar: godkannbar.ok,
    balansGodkand,
    tacktBehovPct: lage?.tackningPct,
  });
  const ssgSnitt = genomsnittligSsgPct(api.medarbetare());
  const ssgUtnytt = ssgUtnyttjandePct(null, null);
  const vakanta = timmarEllerTomt(null);
  const vikarie = timmarEllerTomt(null);
  const period = api.underlag().period;
  const sparat = api.sparadInfo();
  const org = visningsNamnVerksamhet(String((state as { org?: string } | null)?.org || ""));

  const blockerare = [
    ...(!readiness.ready && lageId === "fore" ? readiness.blockingReasons : []),
    ...(lageId === "balans" && !godkannbar.ok ? godkannbar.reasons : []),
  ];

  const resurs = lage
    ? {
        intakt: api.kr(lage.intakt),
        schemakostnad: api.kr(lage.kostnad),
        marginal: api.kr(lage.resultat),
        matchning: fmtPct(lage.matchningPct),
        overkapacitet: fmtH(lage.overkapacitetH),
        underkapacitet: fmtH(lage.obemannatH),
        personaltimmar: fmtH(lage.schematidH),
        vakanta: vakanta.text,
        vakantaSaknas: vakanta.saknas,
        genomsnittligSsg: ssgSnitt != null ? `${Math.round(ssgSnitt)} %` : undefined,
        ssgUtnyttjande: ssgUtnytt == null ? undefined : `${ssgUtnytt.toFixed(1)} %`,
        vikarie: vikarie.text,
        vikarieSaknas: vikarie.saknas,
      }
    : undefined;

  const mapped = lage
    ? {
        status: harBalans ? "FEASIBLE" : "NOT_RUN",
        coveragePercent: lage.tackningPct,
        customerNearPercent: lage.kundnaraPct,
        cost: Math.round(lage.kostnad * 100),
        hardViolations: summary?.hardViolations ?? [],
        warnings: summary?.warnings ?? [],
        changedShiftCount: summary?.changedShiftCount ?? 0,
        lockedShiftCount: summary?.lockedShiftCount ?? 0,
        explanationSummary: summary?.explanationSummary || "",
        performanceSummary: "",
      }
    : null;

  const klick = () => {
    if (cta.id === "skapa") void korBemanningsbalans({ api, state });
    else if (cta.id === "granska") api.setTab("resultat");
    else if (cta.id === "godkann") api.godkannBalans?.();
    else if (cta.id === "utfall") api.setTab("nyckeltal");
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Översikt</div>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-deep sm:text-4xl">Bemanningsbalans</h1>
        <p className="mt-2 max-w-2xl text-base leading-relaxed text-muted-foreground">
          {lageInfo.label}. {lageInfo.text}
        </p>
      </div>

      <Card className="rounded-2xl p-4 shadow-lift" data-statusrad="tidslage">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 text-sm">
          <div>
            <dt className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Verksamhet</dt>
            <dd className="font-semibold text-deep">{org}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Schemaperiod</dt>
            <dd className="font-semibold text-deep">
              {period?.from ? `${period.from} – ${period.to}` : "–"}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Aktuellt läge</dt>
            <dd className="font-semibold text-deep">{lageInfo.label}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Status</dt>
            <dd className="font-semibold text-deep">{status}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Senast uppdaterad</dt>
            <dd className="font-semibold text-deep">
              {sparat?.uppdaterad
                ? new Date(sparat.uppdaterad).toLocaleString("sv-SE", { dateStyle: "short", timeStyle: "short" })
                : "–"}
            </dd>
          </div>
        </dl>
      </Card>

      <TreOmraden summary={mapped} hardCount={hard} resurs={resurs} tom={!lage} />

      <Card className="rounded-2xl p-6 shadow-lift">
        <h2 className="text-xl font-extrabold text-deep">Nästa steg</h2>
        <Button
          className="mt-4"
          size="lg"
          data-cta={cta.id}
          disabled={cta.disabled}
          aria-disabled={cta.disabled}
          onClick={klick}
        >
          {cta.id === "skapa" ? <Sparkles /> : cta.id === "godkann" ? <CheckCircle2 /> : <ArrowRight />} {cta.label}
        </Button>
        {blockerare.length ? (
          <ul className="mt-3 space-y-1 text-sm text-warning" aria-live="polite">
            {blockerare.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : null}
        {lage && lage.tackningPct < 100 && lageId === "balans" && lage.obemannatKundbehovH > 0 ? (
          <p className="mt-3 text-sm text-warning">
            {lage.obemannatKundbehovH.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} h kundbehov saknar bemanning.
          </p>
        ) : null}
        <p className="mt-4 text-xs text-muted-foreground" title={TACKT_BEHOV_FORKLARING}>
          {TACKT_BEHOV_FORKLARING}
        </p>
        <p className="mt-1 text-xs text-muted-foreground" title={KUNDNARA_FORKLARING}>
          {KUNDNARA_FORKLARING}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{KAPACITET_FORKLARING}</p>
      </Card>
    </div>
  );
}
