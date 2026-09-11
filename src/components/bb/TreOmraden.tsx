import type { ReactNode } from "react";
import { HeartHandshake, ShieldCheck, Scale } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { MotorUiSummary } from "@/lib/bb/vcFlode";
import { KAPACITET_FORKLARING, KUNDNARA_FORKLARING, TACKT_BEHOV_FORKLARING, vcStatusText } from "@/lib/bb/vcFlode";

function pct(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "–";
  return `${v.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} %`;
}

function kr(ore: number) {
  return `${Math.round(ore / 100).toLocaleString("sv-SE")} kr`;
}

export type ResursSiffror = {
  intakt?: string;
  schemakostnad?: string;
  marginal?: string;
  budgetMotSchema?: string;
  overkapacitet?: string;
  underkapacitet?: string;
  vakanta?: string;
  vakantaSaknas?: boolean;
  genomsnittligSsg?: string;
  ssgUtnyttjande?: string;
  overtids?: string;
  vikarie?: string;
  vikarieSaknas?: boolean;
  korttids?: string;
  kostnadPerTackt?: string;
};

const SAKNAS = new Set(["–", "", undefined]);

export function TreOmraden({
  summary,
  hardCount,
  locked,
  resurs,
  kontinuitet,
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
  const natt = (s?.warnings || []).some((w) => /natt|jour/i.test(`${w.rule} ${w.message}`));

  const kort = (ikon: ReactNode, rubrik: string, rader: { etikett: string; varde: string; title?: string }[], fot?: string) => (
    <Card className="gap-0 rounded-2xl p-6 shadow-lift">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary">{ikon}</span>
        <h3 className="text-lg font-extrabold text-deep">{rubrik}</h3>
      </div>
      <dl className="mt-5 space-y-3">
        {rader.map((r) => (
          <div key={r.etikett} className="flex items-baseline justify-between gap-3" title={r.title}>
            <dt className="text-sm text-muted-foreground">{r.etikett}</dt>
            <dd className="text-base font-bold tabular-nums text-deep">{r.varde}</dd>
          </div>
        ))}
      </dl>
      {fot ? <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{fot}</p> : null}
    </Card>
  );

  const huvudResurs = [
    { etikett: "Intäkt", varde: resurs?.intakt || "–" },
    { etikett: "Schemakostnad", varde: s && s.cost ? kr(s.cost) : resurs?.schemakostnad || "–" },
    { etikett: "Intäkt − schemakostnad", varde: resurs?.marginal || "–" },
    { etikett: "Överkapacitet", varde: resurs?.overkapacitet || "–" },
    { etikett: "Underkapacitet", varde: resurs?.underkapacitet || "–" },
    { etikett: "Genomsnittlig SSG", varde: resurs?.genomsnittligSsg || "–" },
    ...(resurs?.ssgUtnyttjande
      ? [{ etikett: "SSG-utnyttjande", varde: resurs.ssgUtnyttjande }]
      : []),
    {
      etikett: "Vakanta timmar",
      varde: resurs?.vakantaSaknas ? "–" : resurs?.vakanta || "–",
      title: resurs?.vakantaSaknas ? "Vakanta timmar saknas i underlaget" : undefined,
    },
    {
      etikett: "Vikarieanvändning",
      varde: resurs?.vikarieSaknas ? "–" : resurs?.vikarie || "–",
      title: resurs?.vikarieSaknas ? "Vikarietimmar saknas i underlaget" : undefined,
    },
    { etikett: "Kostnad per täckt kundtimme", varde: resurs?.kostnadPerTackt || "–" },
  ].filter((r) => !(r.etikett === "Kostnad per täckt kundtimme" && SAKNAS.has(r.varde)));

  const saknasRader = [
    { etikett: "Kontinuitet", varde: kontinuitet },
    { etikett: "Budget mot schemakostnad", varde: resurs?.budgetMotSchema },
    { etikett: "Övertid/mertid", varde: resurs?.overtids },
    { etikett: "Korttidsfrånvaro", varde: resurs?.korttids },
  ].filter((r) => r.varde && !SAKNAS.has(r.varde));

  const kundRader = [
    { etikett: "Täckt behov", varde: tom ? "–" : pct(s?.coveragePercent), title: TACKT_BEHOV_FORKLARING },
    { etikett: "Kundnära tid", varde: tom ? "–" : pct(s?.customerNearPercent), title: KUNDNARA_FORKLARING },
  ];
  if (kontinuitet && !SAKNAS.has(kontinuitet)) {
    kundRader.push({ etikett: "Kontinuitet", varde: kontinuitet, title: undefined });
  }

  return (
    <div className={cn("grid gap-4 lg:grid-cols-3", tom && "opacity-90")}>
      {kort(<HeartHandshake className="size-5" />, "Kundnytta", kundRader)}
      {kort(<ShieldCheck className="size-5" />, "Hållbar bemanning", [
        { etikett: "Hårda regelbrott", varde: String(hard) },
        { etikett: "Arbetsmiljövarningar", varde: String(warn) },
        { etikett: "Låsta pass", varde: String(locked ?? s?.lockedShiftCount ?? 0) },
        { etikett: "Natt/jour", varde: natt ? "Varning finns" : "Ingen varning" },
      ])}
      {kort(<Scale className="size-5" />, "Rätt resurser i rätt tid", huvudResurs, KAPACITET_FORKLARING)}
      {saknasRader.length ? (
        <p className="lg:col-span-3 text-xs text-muted-foreground">
          Data saknas: {["Kontinuitet", "Övertid/mertid", "Korttidsfrånvaro", "Budget mot schemakostnad"].join(", ")}.
        </p>
      ) : (
        <p className="lg:col-span-3 text-xs text-muted-foreground">Data saknas för kontinuitet, övertid, korttidsfrånvaro och budget.</p>
      )}
      {s?.explanationSummary ? (
        <p className="lg:col-span-3 text-sm leading-relaxed text-muted-foreground">
          <span className="font-semibold text-deep">Förklaring. </span>
          {s.explanationSummary} {vcStatusText(s.status)}.
        </p>
      ) : null}
    </div>
  );
}
