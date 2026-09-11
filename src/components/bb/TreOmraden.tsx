import type { ReactNode } from "react";
import { HeartHandshake, ShieldCheck, Scale } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { MotorUiSummary } from "@/lib/bb/vcFlode";
import {
  KAPACITET_FORKLARING,
  KUNDNARA_FORKLARING,
  MATCHNING_FORKLARING,
  OVERKAPACITET_FORKLARING,
  TACKT_BEHOV_FORKLARING,
  TRE_OMRADEN_RUBRIKER,
  UNDERKAPACITET_FORKLARING,
} from "@/lib/bb/vcFlode";

function pct(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "–";
  return `${v.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} %`;
}

export type ResursSiffror = {
  intakt?: string;
  schemakostnad?: string;
  marginal?: string;
  matchning?: string;
  overkapacitet?: string;
  underkapacitet?: string;
  personaltimmar?: string;
  vakanta?: string;
  vakantaSaknas?: boolean;
  genomsnittligSsg?: string;
  ssgUtnyttjande?: string;
  overtids?: string;
  vikarie?: string;
  vikarieSaknas?: boolean;
};

export function TreOmraden({
  summary,
  hardCount,
  resurs,
  tom,
  fel,
  laddar,
}: {
  summary: MotorUiSummary | null;
  hardCount?: number;
  locked?: number;
  resurs?: ResursSiffror;
  kontinuitet?: string;
  tom?: boolean;
  fel?: string;
  laddar?: boolean;
}) {
  if (laddar) {
    return (
      <p className="rounded-2xl border border-border bg-card px-5 py-8 text-center text-sm text-muted-foreground" role="status">
        Hämtar översikten…
      </p>
    );
  }
  if (fel) {
    return (
      <p className="rounded-2xl border border-destructive/30 bg-danger-soft px-5 py-6 text-sm text-destructive" role="alert">
        {fel}
      </p>
    );
  }
  const s = summary;
  const hard = hardCount ?? s?.hardViolations.length ?? 0;
  const warn = s?.warnings.length ?? 0;
  const allaRegler = [...(s?.hardViolations || []), ...(s?.warnings || [])];
  const antalRegel = (re: RegExp) => {
    const n = allaRegler.filter((w) => re.test(`${w.rule || ""} ${w.message || ""}`)).length;
    return n ? String(n) : "Ingen varning";
  };
  const natt = allaRegler.some((w) => /natt|jour/i.test(`${w.rule || ""} ${w.message || ""}`));

  const kort = (ikon: ReactNode, rubrik: string, rader: { etikett: string; varde: string; title?: string; indent?: boolean }[], fot?: string) => (
    <Card className="gap-0 rounded-2xl p-6 shadow-lift" data-omrade={rubrik}>
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">{ikon}</span>
        <h3 className="text-lg font-extrabold text-deep">{rubrik}</h3>
      </div>
      <dl className="mt-5 space-y-3">
        {rader.map((r) => (
          <div key={r.etikett} className={cn("flex items-baseline justify-between gap-3", r.indent && "pl-4")} title={r.title}>
            <dt className="text-sm text-muted-foreground">{r.indent ? `↳ ${r.etikett}` : r.etikett}</dt>
            <dd className="text-base font-bold tabular-nums text-deep">{r.varde}</dd>
          </div>
        ))}
      </dl>
      {fot ? <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{fot}</p> : null}
    </Card>
  );

  const resursRader = [
    { etikett: "Matchning mot behov", varde: resurs?.matchning || "–", title: MATCHNING_FORKLARING },
    { etikett: "Underkapacitet", varde: resurs?.underkapacitet || "–", title: UNDERKAPACITET_FORKLARING, indent: true },
    { etikett: "Överkapacitet", varde: resurs?.overkapacitet || "–", title: OVERKAPACITET_FORKLARING, indent: true },
    { etikett: "Planerade personaltimmar", varde: resurs?.personaltimmar || "–" },
    { etikett: "Personalkostnad", varde: resurs?.schemakostnad || "–" },
    { etikett: "Intäkt", varde: resurs?.intakt || "–" },
    { etikett: "Intäkt − schemakostnad", varde: resurs?.marginal || "–" },
    ...(resurs?.ssgUtnyttjande ? [{ etikett: "SSG-utnyttjande", varde: resurs.ssgUtnyttjande }] : []),
    {
      etikett: "Vakanta timmar",
      varde: resurs?.vakantaSaknas ? "–" : resurs?.vakanta || "–",
      title: resurs?.vakantaSaknas ? "Vakanta timmar saknas i underlaget" : undefined,
    },
    {
      etikett: "Vikarietimmar",
      varde: resurs?.vikarieSaknas ? "–" : resurs?.vikarie || "–",
      title: resurs?.vikarieSaknas ? "Vikarietimmar saknas i underlaget" : undefined,
    },
    ...(resurs?.overtids ? [{ etikett: "Övertid/mertid", varde: resurs.overtids }] : []),
  ];

  return (
    <div className={cn("grid gap-4 lg:grid-cols-3", tom && "opacity-90")} data-huvudomraden="3">
      {kort(<HeartHandshake className="size-5" />, TRE_OMRADEN_RUBRIKER[0], [
        { etikett: "Täckt behov", varde: tom ? "–" : pct(s?.coveragePercent), title: TACKT_BEHOV_FORKLARING },
        { etikett: "Kundnära tid", varde: tom ? "–" : pct(s?.customerNearPercent), title: KUNDNARA_FORKLARING },
      ])}
      {kort(<ShieldCheck className="size-5" />, TRE_OMRADEN_RUBRIKER[1], [
        { etikett: "Hårda regelbrott", varde: hard === 0 ? "0 hårda regelbrott" : String(hard) },
        { etikett: "Dygnsvila", varde: antalRegel(/dygnsvila/i) },
        { etikett: "Veckovila", varde: antalRegel(/veckovila/i) },
        { etikett: "Fridagar", varde: antalRegel(/fridag/i) },
        { etikett: "Natt/jour-belastning", varde: natt ? "Varning finns" : "Ingen varning" },
        { etikett: "Mjuka arbetsmiljövarningar", varde: String(warn) },
      ], hard === 0 ? "0 hårda regelbrott." : undefined)}
      {kort(<Scale className="size-5" />, TRE_OMRADEN_RUBRIKER[2], resursRader, KAPACITET_FORKLARING)}
    </div>
  );
}
