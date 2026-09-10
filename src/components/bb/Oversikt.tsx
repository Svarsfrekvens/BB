import { Heart, User, TrendingUp, Clock, Check, X, ChevronRight, Sparkles, ArrowLeft, Upload, Hourglass } from "lucide-react";
import { fmtH, fmtPct } from "@/lib/bb/vy";
import type { VyApi, VyProps } from "@/lib/bb/vy";
import type { VyData } from "@/lib/bb/typer";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/* Presentationslager för Översikt. Alla tal kommer från beräkningslagret –
 * ingenting räknas om här. */

type Props = VyProps;
/** Vyer som bara ritas när underlaget finns. */
type DataProps = Omit<VyProps, "d"> & { d: VyData };

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Tolk({ ton, children }: { ton: "bra" | "varn" | "neutral"; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "mt-4 flex items-start gap-2 rounded-xl px-3 py-2.5 text-[13px] leading-snug font-semibold",
        ton === "bra" && "bg-success-soft text-success",
        ton === "varn" && "bg-warning-soft text-warning",
        ton === "neutral" && "bg-muted text-deep-soft",
      )}
    >
      {ton === "bra" ? <Check className="mt-0.5 size-4 shrink-0" /> : ton === "varn" ? <span aria-hidden>!</span> : null}
      <span>{children}</span>
    </div>
  );
}

function TomtLage({ api }: { api: VyApi }) {
  return (
    <Card className="mx-auto max-w-xl p-8 text-center">
      <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
        <Upload className="size-6" />
      </div>
      <h2 className="mt-4 text-2xl font-extrabold text-deep">Läs in verksamhetens Excel</h2>
      <p className="mx-auto mt-2 max-w-md text-[15px] text-muted-foreground">
        Välj filen nedan. Appen läser insatserna, kontrollerar dem och räknar fram kundbehov, resursbehov och
        nyckeltal. Inget lämnar din dator.
      </p>
      <Button className="mt-6" onClick={() => api.valjFil()}>
        <Upload /> Välj Excel-fil
      </Button>
    </Card>
  );
}

function Statusband({ d, state, api }: DataProps) {
  const optimerat = !!state.optimerat && api.hasBer();
  const harSchema = api.schematidKalla() === "medvind";
  const lage = api.foreEfter()?.efter ?? api.foreLage();
  const obemannade = lage ? lage.obemannadeIntervall : 0;
  const bemanningPunkt = {
    ok: obemannade === 0,
    txt: obemannade === 0 ? "Alla insatser bemannade" : `${obemannade} halvtimmar saknar bemanning`,
    sub: obemannade === 0 ? `${d.n.antalInsatser} insatser` : `${api.h1(lage ? lage.obemannatH : 0)} obemannat behov`,
  };
  if (optimerat) {
    const andel = api.ber("Planerad kundnära andel") as number | null;
    const mal = (api.ber("Mål kundnära tid") as number) || 0.75;
    const disp = api.ber("Disponibelt utrymme efter ekonomisk reserv");
    const buffert = api.ber("Beslutad bemanningsbuffert – värde");
    const brott = api.regelbrott();
    const andelPct = typeof andel === "number" ? andel * 100 : null;
    const punkter = harSchema
      ? [
          {
            ok: andelPct != null && andelPct >= mal * 100,
            txt: andelPct != null ? `Kundnära tid ${fmtPct(andelPct)}` : "Kundnära tid",
            sub: `mål ${fmtPct(mal * 100)}`,
          },
          { ok: typeof disp === "number" && disp >= 0, txt: "Budget håller", sub: typeof disp === "number" ? `${api.kr(disp)} kvar efter reserv` : "" },
          { ok: typeof buffert === "number" && buffert > 0, txt: "Bemanningsbuffert", sub: typeof buffert === "number" ? api.kr(buffert) : "" },
          bemanningPunkt,
          { ok: brott <= 1, txt: brott === 0 ? "Inga regelbrott" : brott === 1 ? "Inga väsentliga regelbrott" : `${brott} att åtgärda`, sub: "arbetstidsregler" },
        ]
      : [
          { vantar: true, txt: "Kundnära tid", sub: "Kräver schema" },
          { vantar: true, txt: "Budget håller", sub: "Kräver schema" },
          { vantar: true, txt: "Bemanningsbuffert", sub: "Kräver schema" },
          bemanningPunkt,
        ];
    // Badgen får bara visas när varje kort är grönt.
    const allaGrona = punkter.every((p) => !("vantar" in p && p.vantar) && "ok" in p && p.ok);
    return (
      <div className="rounded-3xl border border-success/40 bg-gradient-to-br from-success-soft to-card p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-bold tracking-widest text-success uppercase">
              {state.org || "Verksamhet"} · optimerat schema
            </div>
            <h2 className="mt-1.5 text-2xl font-extrabold text-deep sm:text-3xl">
              Schemat är planerat utifrån kundernas behov
            </h2>
          </div>
          {!harSchema ? (
            <span className="rounded-full border border-border bg-muted px-4 py-2 text-sm font-bold text-muted-foreground">
              Schematid uppskattad ur Sekoia – läs in schemat för riktiga tal
            </span>
          ) : allaGrona ? (
            <span className="flex items-center gap-2 rounded-full border border-success/30 bg-card px-4 py-2 text-sm font-bold text-success">
              <Check className="size-4" /> Alla mål uppfyllda
            </span>
          ) : (
            <span className="rounded-full border border-warning/40 bg-warning-soft px-4 py-2 text-sm font-bold text-warning">
              Kvar att åtgärda innan alla mål är uppfyllda
            </span>
          )}
        </div>


        <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {punkter.map((p) => {
            const s = p as { ok?: boolean; vantar?: boolean; txt: string; sub: string };
            const vantar = !!s.vantar;
            return (
            <div key={s.txt} className={cn("flex items-start gap-3 rounded-2xl border border-border bg-card px-4 py-3 shadow-sm", vantar && "opacity-70")}>
              <span
                className={cn(
                  "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full",
                  vantar ? "bg-muted text-muted-foreground" : s.ok ? "bg-success-soft text-success" : "bg-warning-soft text-warning",
                )}
              >
                {vantar ? <Hourglass className="size-3" /> : s.ok ? <Check className="size-3" /> : <span aria-hidden className="text-[11px] font-bold">!</span>}
              </span>
              <span>
                <strong className={cn("block text-sm font-bold", vantar ? "text-muted-foreground" : "text-deep")}>{s.txt}</strong>
                <span className="block text-xs tabular-nums text-muted-foreground">{s.sub}</span>
              </span>
            </div>
            );
          })}

        </div>
      </div>
    );
  }

  const nu = (api.foreLage() ?? null) as {
    kundnaraAndel: number;
    schematidH: number;
    schemakostnad: number;
    obemannadeIntervall: number;
    overkapacitetH: number;
  } | null;
  const punkter = [
    { txt: `Kundnära tid ${fmtPct(nu ? nu.kundnaraAndel : 0)}`, sub: "av schemalagd tid går till kunderna" },
    { txt: "Schemalagd tid", sub: nu ? `${fmtH(nu.schematidH)} enligt inläst personalschema` : "personalschemat är inte inläst" },
    { txt: "Personalkostnad", sub: nu ? api.kr(nu.schemakostnad) : "" },
    { txt: "Överkapacitet", sub: nu ? `${fmtH(nu.overkapacitetH)} mer personal än behov` : "" },
    { txt: "Obemannat behov", sub: nu ? `${nu.obemannadeIntervall} halvtimmar utan tillräcklig personal` : "" },
  ];
  return (
    <div className="rounded-3xl border border-primary/35 bg-gradient-to-br from-danger-soft to-card p-7 shadow-lift sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <div className="text-[11px] font-bold tracking-widest text-primary uppercase">
            {state.org || "Verksamhet"} · nuläge (ooptimerat)
          </div>
          <h2 className="mt-1.5 text-2xl font-extrabold text-deep sm:text-3xl">Bemanningen följer inte kundernas behov</h2>
          <p className="mt-3 max-w-xl text-sm text-deep-soft">
            Så här ser det ut utan optimering: medarbetare på plats även i lågtimmar, insatser ospridda och låg andel
            kundnära tid. Klicka på <strong>Skapa bemanningsbalans</strong> så optimeras schemat.
          </p>
        </div>
        <span className="rounded-full border border-primary/30 bg-card px-4 py-2 text-sm font-bold text-primary">
          Behöver optimeras
        </span>
      </div>
      <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {punkter.map((s) => (
          <div key={s.txt} className="flex items-start gap-3 rounded-2xl border border-border bg-card px-4 py-3 shadow-sm">
            <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-primary-soft text-primary">
              <X className="size-3" />
            </span>
            <span>
              <strong className="block text-sm font-bold text-deep">{s.txt}</strong>
              <span className="block text-xs tabular-nums text-muted-foreground">{s.sub}</span>
            </span>
          </div>
        ))}
      </div>
      <div className="mt-7 flex flex-wrap items-center gap-4">
        <Button onClick={() => api.skapa()}>
          <Sparkles /> Skapa bemanningsbalans
        </Button>
        <span className="flex items-center gap-2 text-sm font-semibold text-deep-soft">
          <ArrowLeft className="size-4" /> Steg 1: Tryck här för att börja!
        </span>
      </div>
    </div>
  );
}

function Periodval({ state, api }: Props) {
  if (state.importDays <= state.planDays) return null;
  const covers = state.analysisDays <= state.planDays;
  const val = [
    { dagar: state.planDays, label: `Bemanningsplan 1–${state.planDays}` },
    { dagar: state.importDays, label: `Hela importen 1–${state.importDays}` },
  ];
  return (
    <Card className="flex flex-wrap items-center gap-4 p-5">
      <strong className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">Vald period</strong>
      <div className="flex gap-1 rounded-full bg-muted p-1">
        {val.map((v) => (
          <button
            key={v.dagar}
            type="button"
            onClick={() => api.setDagar(v.dagar)}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-bold transition-colors duration-200",
              state.analysisDays === v.dagar ? "bg-card text-deep shadow-lift" : "text-muted-foreground hover:text-deep",
            )}
          >
            {v.label}
          </button>
        ))}
      </div>
      <span className="text-xs text-muted-foreground">Alla vyer räknas om för valet.</span>
      {!covers && (
        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-bold text-warning">
          Dag {state.planDays + 1}–{state.analysisDays} saknar bemanningsplan
        </span>
      )}
    </Card>
  );
}

function Hjulet({ d, state, api }: DataProps) {
  const malAndel = api.hasBer() ? ((api.ber("Mål kundnära tid") as number) || 0.75) * 100 : 75;
  const andel = api.hasBer() && typeof api.ber("Planerad kundnära andel") === "number" ? (api.ber("Planerad kundnära andel") as number) * 100 : null;
  if (!state.optimerat || andel == null) return null;
  const pct = Math.max(0, Math.min(100, andel));
  const R = 52;
  const OMKRETS = 2 * Math.PI * R;
  const naddMal = andel >= malAndel;
  return (
    <Card className="grid gap-7 p-7 lg:grid-cols-[auto_1fr_auto] lg:items-center sm:p-8">
      <div className="mx-auto">
        <svg viewBox="0 0 150 150" width="160" height="160" role="img" aria-label={`Kundnära tid ${api.h1(pct)} procent`}>
          <circle cx="75" cy="75" r={R} fill="none" stroke="var(--muted)" strokeWidth="15" />
          <circle
            cx="75"
            cy="75"
            r={R}
            fill="none"
            stroke={naddMal ? "var(--success)" : "var(--primary)"}
            strokeWidth="15"
            strokeLinecap="round"
            strokeDasharray={OMKRETS.toFixed(1)}
            strokeDashoffset={(OMKRETS * (1 - pct / 100)).toFixed(1)}
            transform="rotate(-90 75 75)"
            style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22,1,0.36,1)" }}
          />
          <text x="75" y="72" textAnchor="middle" fontSize="24" fontWeight="800" fill="var(--deep)">
            {fmtPct(pct)}
          </text>
          <text x="75" y="94" textAnchor="middle" fontSize="11" letterSpacing="1" fill="var(--muted-foreground)">
            KUNDNÄRA
          </text>
        </svg>
      </div>
      <div className="min-w-0">
        <span
          className={cn(
            "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold",
            naddMal ? "bg-success-soft text-success" : "bg-warning-soft text-warning",
          )}
        >
          {naddMal ? <Check className="size-3.5" /> : <span aria-hidden>!</span>}
          {naddMal ? "Verksamheten mår bra" : "Behöver ses över"}
        </span>
        <h2 className="mt-3 text-2xl font-extrabold text-deep">
          {naddMal ? "Tiden går dit den ska – hos kunderna" : "Andelen kundnära tid är under målet"}
        </h2>
        <p className="mt-1.5 text-[15px] text-muted-foreground">
          {fmtPct(pct)} av arbetstiden går till tid hos kunden. Målet är {fmtPct(malAndel)}.
        </p>
        <div className="relative mt-5 h-3 overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full transition-all duration-700", naddMal ? "bg-success" : "bg-primary")}
            style={{ width: `${pct}%` }}
          />
          <div className="absolute top-0 h-full w-0.5 bg-deep/50" style={{ left: `${malAndel}%` }} />
        </div>
        <div className="relative mt-1.5 flex justify-between text-[11px] text-muted-foreground">
          <span>0 %</span>
          <span className="absolute -translate-x-1/2" style={{ left: `${malAndel}%` }}>
            mål {fmtPct(malAndel)}
          </span>
          <span>100 %</span>
        </div>
      </div>
      <div className="flex gap-6 lg:flex-col lg:gap-4 lg:border-l lg:border-border lg:pl-7">
        {[
          { v: fmtH(d.n ? d.n.kundbehovH : 0), l: "Kundbehov" },
          { v: fmtH(api.hasBer() ? ((api.ber("Planerad schematid") as number) || 0) : 0), l: "Schematid" },
        ].map((f) => (
          <div key={f.l}>
            <span className="block text-2xl font-extrabold tabular-nums text-deep">{f.v}</span>
            <span className="block text-xs font-semibold text-muted-foreground">{f.l}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Kpier({ d, state, api }: DataProps) {
  const malAndel = api.hasBer() ? ((api.ber("Mål kundnära tid") as number) || 0.75) * 100 : 75;
  const andelNu = api.hasBer() && typeof api.ber("Planerad kundnära andel") === "number" ? (api.ber("Planerad kundnära andel") as number) * 100 : null;
  const schematidH = api.hasBer() && typeof api.ber("Planerad schematid") === "number" ? (api.ber("Planerad schematid") as number) : state.plannedHours;

  const kort: {
    lab: string;
    val: string;
    note: string;
    Ikon: typeof Heart;
    tolk: { ton: "bra" | "varn" | "neutral"; txt: string };
    hero?: boolean;
  }[] = [
    {
      lab: "Kundbehov",
      val: `${api.h1(d.n.kundbehovH)} h`,
      note: `${d.n.antalInsatser} insatser · varav Gemensamt ${api.h1(d.gem ? d.gem.kundbehovH : 0)} h`,
      Ikon: Heart,
      tolk: { ton: "neutral", txt: "Så mycket tid kunderna behöver den här perioden" },
      hero: true,
    },
    {
      lab: "Personalbehov inkl. dubbel",
      val: `${api.h1(d.n.personalbehovH)} h`,
      note: `Extra dubbelbemanning ${api.h1(d.n.extraDubbelH)} h · ${d.n.dubbelbemannadeRader} rader`,
      Ikon: User,
      tolk: { ton: "neutral", txt: `Behovet + tid när två måste hjälpas åt (${api.h1(d.n.extraDubbelH)} h extra)` },
    },
    {
      lab: "Dimensionerande resursbehov",
      val: `${api.h1(d.resursH)} h`,
      note: d.fil
        ? `Samtidighet per 15 min (verksamhetens modell) · topp ${d.fil.peak.value} kl. ${d.fil.peak.tid} ${d.fil.peak.datum}`
        : `Appens 30-min-beräkning · topp ${api.h1(d.curve.topp.rabehov)} (dim. ${d.curve.topp.dimensionerat}) ${d.curve.topp.datum} kl. ${d.curve.topp.klockan}`,
      Ikon: TrendingUp,
      tolk: { ton: "neutral", txt: "Så många behöver jobba samtidigt när det är som mest" },
    },
    {
      lab: "Planerad schematid",
      val: `${api.h1(schematidH)} h`,
      note: api.hasBer() ? "Verksamhetens egen schematid" : `Kostnad ${api.kr(d.eco.planeradKostnad)}`,
      Ikon: Clock,
      tolk:
        state.optimerat && andelNu != null
          ? {
              ton: andelNu >= malAndel ? "bra" : "varn",
              txt: `${fmtPct(andelNu)} går till tid hos kunden — ${
                andelNu >= malAndel ? `över målet ${fmtPct(malAndel)}` : `under målet ${fmtPct(malAndel)}`
              }`,
            }
          : { ton: "neutral", txt: "Total inplanerad arbetstid för perioden" },
    },
  ];

  return (
    <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
      {kort.map((k, i) => (
        <Card
          key={k.lab}
          className="bb-rise flex flex-col gap-0 p-7 transition-shadow duration-200 hover:shadow-lift-lg"
          style={{ animationDelay: `${i * 70}ms` }}
        >
          <div
            className={cn(
              "grid size-11 place-items-center rounded-2xl",
              k.hero ? "bg-primary-soft text-primary" : "bg-muted text-deep-soft",
            )}
          >
            <k.Ikon className="size-5" />
          </div>
          <div className="mt-5 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{k.lab}</div>
          <div
            className={cn(
              "mt-2 text-4xl leading-none font-extrabold tracking-tight tabular-nums",
              k.hero ? "text-primary" : "text-deep",
            )}
          >
            {k.val}
          </div>
          <p className="mt-3 text-[13px] leading-snug text-muted-foreground">{k.note}</p>
          <div className="mt-auto">
            <Tolk ton={k.tolk.ton}>{k.tolk.txt}</Tolk>
          </div>
        </Card>
      ))}
    </div>
  );
}

const FLODE = [
  { t: "Kundbehov", u: "vad kunderna behöver", tab: "kundbehov" },
  { t: "Tid", u: "när insatserna sker", tab: "sprid" },
  { t: "Resursbehov", u: "hur många samtidigt", tab: "resurskurva" },
  { t: "Bemanning", u: "vem som jobbar", tab: "personal" },
  { t: "Schema", u: "färdigt pass-schema", tab: "schema" },
  { t: "Uppföljning", u: "mål & kontroll", tab: "nyckeltal" },
];

function Grundflode({ api }: { api: VyApi }) {
  return (
    <Card className="p-7 sm:p-8">
      <Eyebrow>Grundflöde</Eyebrow>
      <h2 className="mt-1.5 text-xl font-extrabold text-deep">Från kundens behov till ett hållbart schema</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Klicka på ett steg för att öppna det. Samma logik som i Excel – samlad i ett arbetsflöde.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {FLODE.map((s, i) => (
          <button
            key={s.tab}
            type="button"
            onClick={() => api.setTab(s.tab)}
            className="group flex flex-col items-center gap-2 rounded-2xl px-2 py-3 text-center transition-colors duration-200 hover:bg-muted"
          >
            <span className="grid size-11 place-items-center rounded-full bg-deep text-sm font-extrabold text-white transition-colors duration-200 group-hover:bg-primary">
              {i + 1}
            </span>
            <span className="text-sm font-bold text-deep">{s.t}</span>
            <span className="text-xs text-muted-foreground">{s.u}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function Daggraf({ state, api }: Props) {
  if (!state.optimerat || !state.period) return null;
  const dagar: string[] = [];
  for (let i = 0; i < 7 && i < state.importDays; i++) dagar.push(api.addDays(state.period.from, i));
  const kbByDay: Record<string, number> = {};
  const stByDay: Record<string, number> = {};
  for (const r of api.arbetsRader()) {
    if (!r.datum) continue;
    kbByDay[r.datum] = (kbByDay[r.datum] || 0) + (r.minuter || 0) / 60;
  }
  if (state.individschema)
    for (const x of state.individschema.rows) {
      const iso = api.cellToIso(x["Datum"]);
      const h = Number(x["Betald tid h"]) || 0;
      if (iso) stByDay[iso] = (stByDay[iso] || 0) + h;
    }
  const veckodag = ["sön", "mån", "tis", "ons", "tor", "fre", "lör"];
  const serie = dagar.map((iso) => {
    const dt = new Date(iso + "T12:00:00Z");
    return { iso, dag: veckodag[dt.getUTCDay()], kb: kbByDay[iso] || 0, st: stByDay[iso] || 0 };
  });
  const maxV = Math.max(1, ...serie.map((s) => Math.max(s.kb, s.st)));
  let gap: { dag: string | undefined; kb: number; st: number; g: number } | null = null;
  for (const s of serie) {
    const g = s.st - s.kb;
    if (!gap || g < gap.g) gap = { ...s, g };
  }
  return (
    <Card className="p-7 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Eyebrow>Vecka 1</Eyebrow>
          <h2 className="mt-1.5 text-xl font-extrabold text-deep">Behov och planerad tid per dag</h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            Schematiden täcker kundbehovet varje dag – med marginal för rapport, förflyttning och dubbelbemanning.
          </p>
        </div>
        <div className="flex gap-4 text-xs font-semibold text-muted-foreground">
          <span className="flex items-center gap-2">
            <i className="size-3 rounded-sm bg-primary" /> Kundbehov
          </span>
          <span className="flex items-center gap-2">
            <i className="size-3 rounded-sm bg-deep" /> Schematid
          </span>
        </div>
      </div>
      <div className="mt-6 flex h-52 items-end gap-3">
        {serie.map((s) => (
          <div key={s.iso} className="flex flex-1 flex-col items-center gap-2">
            <div className="flex h-44 w-full items-end justify-center gap-1">
              <i
                title={`${s.dag}: behov ${api.h1(s.kb)} h`}
                className="w-1/3 rounded-t-md bg-primary transition-all duration-500"
                style={{ height: `${(s.kb / maxV) * 100}%` }}
              />
              <i
                title={`${s.dag}: schematid ${api.h1(s.st)} h`}
                className="w-1/3 rounded-t-md bg-deep transition-all duration-500"
                style={{ height: `${(s.st / maxV) * 100}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-muted-foreground">{s.dag}</span>
          </div>
        ))}
      </div>
      {gap && (
        <Tolk ton={gap.g >= 0 ? "bra" : "varn"}>
          Tätast marginal på {gap.dag}dag: {api.h1(gap.st)} h schematid mot {api.h1(gap.kb)} h kundbehov.
        </Tolk>
      )}
    </Card>
  );
}

function Beslutsstod({ state, api }: Props) {
  const punkter: { txt: string; meta: string; tab: string; ton: "röd" | "gul" }[] = [];
  if (state.kontroller)
    for (const r of state.kontroller) {
      if (/^pass$/i.test(r.status)) continue;
      punkter.push({
        txt: r.kontroll,
        meta: r.atgard || String(r.status || ""),
        tab: "atgarder",
        ton: /åtgärd/i.test(r.status) ? "röd" : "gul",
      });
    }
  if (state.optimerat) {
    const brott = api.regelbrott();
    if (brott > 0)
      punkter.push({
        txt: "Regelvarningar i schemat",
        meta: brott + " att se över (dygnsvila, nattbehörighet m.m.)",
        tab: "schema",
        ton: "gul",
      });
  }
  if (!punkter.length) {
    if (!state.optimerat) return null;
    return (
      <Card className="p-7">
        <Eyebrow>Beslutsstöd</Eyebrow>
        <Tolk ton="bra">Inget kräver åtgärd just nu – schemat uppfyller målen.</Tolk>
      </Card>
    );
  }
  const visa = punkter.slice(0, 6);
  return (
    <Card className="p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Eyebrow>Beslutsstöd</Eyebrow>
          <h2 className="mt-1.5 text-xl font-extrabold text-deep">Det här kan VC titta på</h2>
        </div>
        <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-bold text-warning">
          {punkter.length} punkter
        </span>
      </div>
      <div className="mt-5 flex flex-col gap-1">
        {visa.map((p, i) => (
          <button
            key={p.txt + i}
            type="button"
            onClick={() => api.setTab(p.tab)}
            className="flex items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors duration-200 hover:bg-muted"
          >
            <span className={cn("size-2.5 shrink-0 rounded-full", p.ton === "röd" ? "bg-primary" : "bg-warning")} />
            <span className="min-w-0 flex-1">
              <strong className="block text-sm font-bold text-deep">{p.txt}</strong>
              <span className="block truncate text-xs text-muted-foreground">{p.meta}</span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
          </button>
        ))}
      </div>
      {punkter.length > 6 && (
        <Button variant="outline" size="sm" className="mt-4" onClick={() => api.setTab("atgarder")}>
          Visa alla {punkter.length} åtgärder
        </Button>
      )}
    </Card>
  );
}

function Ekonomirad({ d, state, api }: DataProps) {
  const filEko = api.hasBer();
  const t10 = (v: unknown) => (typeof v === "number" ? api.kr(v) : "–");
  const rader: [string, string, string][] = filEko
    ? [
        ["Månadsintäkt", t10(api.ber("Månadsintäkt")), "Datumstyrd ersättning per kund"],
        ["Ren schemakostnad", t10(api.ber("Ren schemakostnad")), "Schematid × timkostnad"],
        ["Total kostnadsprognos", t10(api.ber("Total kostnadsprognos")), "Inkl. korttidsfrånvaro"],
        ["Ekonomisk reserv", t10(api.ber("Ekonomisk reserv")), "6 % av budgeten"],
        ["Disponibelt efter reserv", t10(api.ber("Disponibelt utrymme efter ekonomisk reserv")), "Se fliken Ekonomi för detaljer"],
      ]
    : [
        ["Planerad kostnad", api.kr(d.eco.planeradKostnad), "Planerade timmar × timkostnad"],
        ["Planerad överkapacitet", `${api.h1(d.eco.planeradOverkapacitetH)} h`, "Planerade timmar − dimensionerande behov"],
        ["Korttidsfrånvaro", api.kr((d.eco.planeradKostnad * state.absencePct) / 100), `${state.absencePct} % av kostnaden`],
        ["Ekonomisk reserv", api.kr((state.budget * state.reservePct) / 100), `${state.reservePct} % av budgeten`],
        [
          "Disponibelt efter reserv",
          api.kr(state.budget - d.eco.planeradKostnad * (1 + state.absencePct / 100) - (state.budget * state.reservePct) / 100),
          `Budget ${api.kr(state.budget)}`,
        ],
      ];
  const disp = filEko ? api.ber("Disponibelt utrymme efter ekonomisk reserv") : null;
  return (
    <Card className="p-7 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Eyebrow>{filEko ? "Ekonomi (verksamhetens egna tal, hela perioden)" : "Ekonomi för vald period"}</Eyebrow>
        {filEko && (
          <Button variant="outline" size="sm" onClick={() => api.setTab("ekonomi")}>
            Öppna ekonomi
          </Button>
        )}
      </div>
      {typeof disp === "number" && (
        <Tolk ton={disp >= 0 ? "bra" : "varn"}>
          {disp >= 0 ? `Budgeten håller med ${api.kr(disp)} i marginal efter reserv` : `Budgeten överskrids med ${api.kr(-disp)}`}
        </Tolk>
      )}
      <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-5">
        {rader.map(([l, v, note]) => (
          <div key={l}>
            <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{l}</div>
            <div className="mt-1 text-xl font-extrabold tabular-nums text-deep">{v}</div>
            <div className="mt-1 text-xs text-muted-foreground">{note}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function Oversikt({ d, state, api }: Props) {
  if (!d) return <TomtLage api={api} />;
  const p = { d, state, api };
  const daggraf = <Daggraf {...p} />;
  const beslutsstod = <Beslutsstod {...p} />;
  return (
    <div className="flex flex-col gap-7">
      <Statusband {...p} />
      <Periodval {...p} />
      <Hjulet {...p} />
      <Kpier {...p} />
      {state.optimerat ? (
        <div className="grid gap-7 xl:grid-cols-[2fr_1fr]">
          <div>{daggraf}</div>
          <div>{beslutsstod}</div>
        </div>
      ) : (
        <Grundflode api={api} />
      )}
      <Ekonomirad {...p} />
    </div>
  );
}
