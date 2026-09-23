import { useSyncExternalStore } from "react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { VyProps } from "@/lib/bb/vy";
import { TreOmraden } from "./TreOmraden";
import { Uppladdning } from "./Uppladdning";
import { Startsida } from "./Startsida";
import { hamtaStartlage, lyssnaStartlage, sattStartlage } from "@/lib/bb/startlage";
import { hemAteruppta } from "@/lib/bb/linjartFlode";
import {
  godkannBeslutFranVy,
  behoverUppmarksamhet,
  konfigureratKundnaraMalPct,
  raknaSaknadeKompetenskrav,
  genomsnittligSsgPct,
  getTidslage,
  hemStatusText,
  lasMotorSummary,
  readinessFranApi,
  ssgUtnyttjandePct,
  tidslageText,
  timmarEllerTomt,
  visningsNamnVerksamhet,
} from "@/lib/bb/vcFlode";
import { fmtH, fmtPct } from "@/lib/bb/vy";
import { lasJourDiagnos, visaJourResursbrist, harMjukKundbrist } from "@/lib/bb/jourDiagnos";
import { ResursbristPanel, resursbristProps } from "./ResursbristPanel";
import { BalansPagar } from "./BalansPagar";

export function Hem(props: VyProps) {
  const { api, state, d } = props;
  const startlage = useSyncExternalStore(lyssnaStartlage, hamtaStartlage, hamtaStartlage);
  const sparatInfo = api.sparadInfo();
  if (startlage === "start") {
    return (
      <Startsida
        onKundFil={api.hanteraFil}
        onSchemaFil={api.hanteraSchemaFil}
        onFortsatt={() => {
          sattStartlage("app");
          const u = api.underlag();
          api.setTab(
            hemAteruppta({
              harKundrader: !!u.sekoia,
              kundGodkand: u.godkand.kund,
              harSchema: !!u.schema,
              schemaGodkand: u.godkand.schema,
              harBalans: api.harBalans(),
              balansGodkand: Boolean((props.state as { balansGodkand?: boolean } | null)?.balansGodkand),
            }).tab,
          );
        }}
      />
    );
  }
  if (startlage === "upload") {
    return <Uppladdning {...props} />;
  }

  if (!api.underlag().godkand.kund) {
    const tillUnderlag = () => sattStartlage("upload");
    return (
      <div className="space-y-10">
        <p className="max-w-2xl text-[17px] leading-relaxed text-muted-foreground">
          Inget underlag är inläst ännu. Första steget i processen är Underlag.
        </p>
        <TreOmraden summary={null} tom />
        <Card className="card-lift rounded-[28px] border-transparent bg-gradient-to-br from-white to-primary-soft/35 p-10 shadow-lift-lg">
          <h2 className="text-[28px] font-extrabold text-deep">Nästa steg</h2>
          <p className="mt-4 max-w-xl text-[16px] leading-relaxed text-muted-foreground">Ladda upp underlag för att komma vidare.</p>
          <Button className="mt-7 h-14 rounded-2xl px-8 text-[16px]" size="lg" onClick={tillUnderlag}>
            <ArrowRight /> Fortsätt →
          </Button>
        </Card>
      </div>
    );
  }

  const readiness = readinessFranApi(api);
  const summary = lasMotorSummary(api.motorResultat());
  const fe = api.foreEfter();
  const harBalans = api.harBalans();
  const ofull = Boolean(fe?.ofullstandig);
  const jour = lasJourDiagnos((api.motorResultat() as { resourceDiagnostics?: unknown } | null)?.resourceDiagnostics);
  const jourBrist = visaJourResursbrist(jour);
  const jobb = api.motorJobb?.();
  const pagaende = Boolean(jobb?.id && jobb.phase !== "completed" && jobb.phase !== "failed");
  const lageId = getTidslage({ harBalans, harUtfall: false });
  const lageInfo = tidslageText(lageId);
  const lage = harBalans && !ofull ? fe?.efter ?? api.foreLage() : api.foreLage() ?? fe?.fore;
  const hard = api.regelbrott();
  const godkannbar = godkannBeslutFranVy({
    motorJobb: api.motorJobb?.(),
    motorResultat: api.motorResultat(),
    tacktBehovPct: harBalans && !ofull ? lage?.tackningPct : null,
    hardViolations: harBalans && !jourBrist ? hard : 0,
    saknadeKompetenskrav: harBalans
      ? raknaSaknadeKompetenskrav([...(summary?.hardViolations || []), ...(summary?.warnings || [])])
      : 0,
    jourResursbrist: jourBrist,
  });
  const balansGodkand = Boolean(state && (state as { balansGodkand?: boolean }).balansGodkand);
  const status = hemStatusText({
    lage: lageId,
    ready: readiness.ready,
    blockingReasons: readiness.blockingReasons,
    godkannbar: godkannbar.ok,
    balansGodkand,
    tacktBehovPct: lage?.tackningPct ?? null,
    pagaende,
    klarForGranskning: harBalans && !pagaende && !ofull && !jourBrist,
  });
  const ssgSnitt = genomsnittligSsgPct(api.medarbetare());
  const ssgUtnytt = ssgUtnyttjandePct(null, null);
  const vakanta = timmarEllerTomt(null);
  const vikarie = timmarEllerTomt(null);
  const period = api.underlag().period;
  const sparat = sparatInfo;
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
        vikarie: vikarie.text,
        vikarieSaknas: vikarie.saknas,
        ...(ssgSnitt != null ? { genomsnittligSsg: `${Math.round(ssgSnitt)} %` } : {}),
        ...(ssgUtnytt == null ? {} : { ssgUtnyttjande: `${ssgUtnytt.toFixed(1)} %` }),
      }
    : undefined;

  const mapped = lage
    ? {
        status: harBalans && !ofull ? "FEASIBLE" : "NOT_RUN",
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

  const malPct = konfigureratKundnaraMalPct({
    varde: typeof api.ber?.("Mål kundnära tid") === "number" ? (api.ber("Mål kundnära tid") as number) : null,
    definition: api.berDef?.("Mål kundnära tid"),
  });
  const uppmarksamhet =
    lageId === "fore" && lage
      ? behoverUppmarksamhet({
          hardViolations: hard,
          underkapacitetH: lage.obemannatH,
          overkapacitetH: lage.overkapacitetH,
          tacktBehovPct: lage.tackningPct,
        })
      : [];

  const ateruppta = hemAteruppta({
    harKundrader: !!(api.underlag().sekoia || (Array.isArray(state["rows"]) && (state["rows"] as unknown[]).length)),
    kundGodkand: api.underlag().godkand.kund,
    harSchema: !!api.underlag().schema,
    schemaGodkand: api.underlag().godkand.schema,
    harBalans,
    balansGodkand,
  });
  const klick = () => {
    if (pagaende) {
      document.querySelector("[data-balans-jobb]")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    api.setTab(ateruppta.tab);
  };

  return (
    <div className="space-y-8">
      <div>
        <p className="max-w-2xl text-[17px] leading-relaxed text-muted-foreground">{lageInfo.text}</p>
      </div>

      {state.importDays > state.planDays ? (
        <Card className="flex flex-wrap items-center gap-4 p-5">
          <strong className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Vald period</strong>
          <div className="flex gap-1 rounded-full bg-muted p-1">
            {[
              { dagar: state.planDays, label: `Bemanningsplan 1–${state.planDays}` },
              { dagar: state.importDays, label: `Hela importen 1–${state.importDays}` },
            ].map((v) => (
              <button
                key={v.dagar}
                type="button"
                onClick={() => api.setDagar(v.dagar)}
                className={cn(
                  "rounded-full px-4 py-2 text-sm font-bold transition-colors",
                  state.analysisDays === v.dagar ? "bg-card text-deep shadow-lift" : "text-muted-foreground hover:text-deep",
                )}
              >
                {v.label}
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      <Card className="card-lift rounded-[28px] p-7" data-statusrad="tidslage" data-nulagekort="oversikt">
        <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <dt className="text-[13px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">Verksamhet</dt>
            <dd className="mt-1.5 text-[16px] font-semibold text-deep">{org}</dd>
          </div>
          <div>
            <dt className="text-[13px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">Schemaperiod</dt>
            <dd className="mt-1.5 text-[16px] font-semibold text-deep">
              {period?.from ? `${period.from} – ${period.to}` : "–"}
            </dd>
          </div>
          <div>
            <dt className="text-[13px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">Aktuellt läge</dt>
            <dd className="mt-1.5 text-[16px] font-semibold text-deep">{lageInfo.label}</dd>
          </div>
          <div>
            <dt className="text-[13px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">Status</dt>
            <dd className="mt-1.5 text-[16px] font-semibold text-deep">{status}</dd>
          </div>
          <div>
            <dt className="text-[13px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">Senast uppdaterad</dt>
            <dd className="mt-1.5 text-[16px] font-semibold text-deep">
              {sparat?.uppdaterad
                ? new Date(sparat.uppdaterad).toLocaleString("sv-SE", { dateStyle: "short", timeStyle: "short" })
                : "–"}
            </dd>
          </div>
        </dl>
      </Card>

      <BalansPagar job={jobb} />

      <ResursbristPanel
        diagnos={jour}
        visaKundbrist={harMjukKundbrist({
          tacktBehovPct: ofull ? null : lage?.tackningPct,
          obemannadeAntal: fe?.obemannade?.length,
          ofullstandigUtanSchema: ofull,
        })}
        {...resursbristProps(api, state)}
      />

      {ofull ? null : (
      <TreOmraden
        /* KUNDNARA_FORKLARING och TACKT_BEHOV_FORKLARING visas i TreOmraden. */
        summary={mapped}
        hardCount={hard}
        tom={!lage}
        {...(resurs ? { resurs } : {})}
        {...(lage
          ? {
              kundnaraExtra: {
                kundbehov: d ? fmtH(d.n.kundbehovH) : fmtH(lage.kundbehovH),
                ...(d ? { insatser: String(d.n.antalInsatser) } : {}),
                forklaring: malPct
                  ? `Mål ${fmtPct(malPct)} enligt verksamhetens konfiguration.`
                  : `${fmtH(lage.kundnaraH)} av ${fmtH(lage.schematidH)} schemalagda timmar är klassificerade som kundnära.`,
              },
            }
          : {})}
      />
      )}

      {lageId === "fore" && uppmarksamhet.length ? (
        <Card className="rounded-2xl p-6 shadow-lift">
          <h2 className="text-lg font-extrabold text-deep">Behöver uppmärksamhet</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Detta blockerar inte Skapa balans. Det är skäl till att skapa Balans.
          </p>
          <ul className="mt-3 space-y-1 text-sm text-deep">
            {uppmarksamhet.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card className="card-lift rounded-[28px] border-transparent bg-gradient-to-br from-white to-primary-soft/35 p-10 shadow-lift-lg">
        <h2 className="text-[28px] font-extrabold text-deep">Nästa steg</h2>
        <p className="mt-4 max-w-xl text-[16px] leading-relaxed text-muted-foreground">
          {ateruppta.label}. {status}
        </p>
        <Button
          className="mt-7 h-14 rounded-2xl px-8 text-[16px]"
          size="lg"
          data-cta={ateruppta.tab}
          onClick={klick}
        >
          <ArrowRight /> {ateruppta.label}
        </Button>
        {blockerare.length ? (
          <ul className="mt-3 space-y-1 text-sm text-warning" aria-live="polite">
            {blockerare.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : null}
        {lage && lage.tackningPct < 100 && lageId === "balans" && !ofull && !jourBrist ? (
          <p className="mt-3 text-sm font-semibold text-warning" data-ej-godkannbar="true">
            Balans kan inte godkännas
            {lage.obemannatKundbehovH > 0
              ? ` – ${lage.obemannatKundbehovH.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} timmar kundbehov återstår att bemanna.`
              : " – kundbehov återstår att bemanna."}
          </p>
        ) : null}
      </Card>
    </div>
  );
}
