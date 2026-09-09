import { useMemo } from "react";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { VyProps } from "@/lib/bb/vy";
import type { KurvSlot } from "@/lib/bb/typer";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Kpi({ etikett, tal, not, i }: { etikett: string; tal: string; not: string; i: number }) {
  return (
    <Card
      className="bb-rise gap-0 rounded-2xl p-6 shadow-lift transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift-lg"
      style={{ animationDelay: `${i * 70}ms` }}
    >
      <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</div>
      <div className="mt-2 text-4xl font-extrabold tracking-tight text-deep tabular-nums">{tal}</div>
      <div className="mt-2 text-sm text-muted-foreground">{not}</div>
    </Card>
  );
}

function Forklaring({ farg, text, linje }: { farg: string; text: string; linje?: boolean }) {
  return (
    <span className="flex items-center gap-2 text-xs text-muted-foreground">
      <i
        className={cn("inline-block rounded-[3px]", linje ? "h-[3px] w-4" : "h-3 w-3")}
        style={{ background: farg }}
      />
      {text}
    </span>
  );
}

export function Resursbehov({ d, state, api }: VyProps) {
  const h1 = api.h1;

  const dagar: string[] = useMemo(() => {
    if (!d) return [];
    const list: string[] = [];
    for (let i = 0; i < state.analysisDays; i++) list.push(api.addDays(d.from, i));
    return list;
  }, [d, state.analysisDays, api]);

  if (!d) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <h2 className="text-xl font-extrabold text-deep">Ingen data ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          Läs in verksamhetens Excel-fil, så visas resurskurvan i 30-minutersintervall här.
        </p>
        <Button className="mt-5" onClick={() => api.valjFil()}>
          <FileText /> Välj Excel-fil
        </Button>
      </Card>
    );
  }

  const index = Math.max(0, Math.min(api.curveDag(), dagar.length - 1));
  const dagIso = dagar[index] ?? "";
  const slots = d.curve.intervall.filter((s) => s.datum === dagIso);

  // Schemalagda medarbetare per 30-minutersintervall (samma modell som förut).
  const bem15 = api.schemaPerSlot(dagIso);
  const bem30: number[] | null = bem15
    ? slots.map((s) => {
        const m = api.clockMin(s.klockan);
        if (m == null) return 0;
        const i0 = Math.floor(m / 15);
        return Math.max(bem15[i0] || 0, bem15[i0 + 1] || 0);
      })
    : null;
  const bemMax = bem30 ? Math.max(0, ...bem30) : 0;
  const bemMin = bem30 && bemMax > 0 ? Math.min(...bem30.filter((x) => x > 0)) : 0;
  const skala = Math.max(1, ...slots.map((s) => Math.max(s.rabehov, s.dimensionerat)), bemMax);
  const tomTopp: KurvSlot = { datum: dagIso, klockan: "", rabehov: 0, medNattgolv: 0, dimensionerat: 0 };
  const dagTopp = slots.reduce((a, s) => (s.rabehov > a.rabehov ? s : a), slots[0] ?? tomTopp);

  const punkter =
    bem30 && bemMax > 0
      ? bem30
          .map((v, i) => `${((i / (bem30.length - 1)) * 100).toFixed(2)},${(100 - (v / skala) * 92).toFixed(2)}`)
          .join(" ")
      : null;

  const natt = (klockan: string) => {
    const t = parseInt(klockan, 10);
    return t >= 22 || t < 6;
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi
          etikett="Dagens topp"
          tal={h1(dagTopp.rabehov)}
          not={`Flest samtidigt behövda kl. ${dagTopp.klockan || "–"}`}
          i={0}
        />
        <Kpi
          etikett="Periodens topp"
          tal={h1(d.curve.topp.rabehov)}
          not={`${d.curve.topp.datum} kl. ${d.curve.topp.klockan} · dimensionerat ${d.curve.topp.dimensionerat}`}
          i={1}
        />
        <Kpi
          etikett="Dimensionerande behov"
          tal={`${h1(d.curve.dimensionerandeDirektResursbehovH)} h`}
          not={
            d.fil
              ? `Appens 30-minutersmodell · verksamhetens egen 15-minutersmodell ${h1(d.resursH)} h`
              : "Summan av behovet med vaken natt som golv"
          }
          i={2}
        />
      </div>

      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>Resurskurva 30 minuter</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Rått och dimensionerande behov</h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Insatsens minuter fördelas jämnt över tidsfönstret – ett långt fönster binder inte en medarbetare hela
              tiden. Vaken natt 22–06 är ett golv, inte ett tillägg.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="icon" disabled={index <= 0} onClick={() => api.setCurveDag(index - 1)}>
                  <ChevronLeft />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Föregående dag</TooltipContent>
            </Tooltip>
            <strong className="min-w-[104px] text-center text-base font-extrabold text-deep tabular-nums">
              {dagIso}
            </strong>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={index >= dagar.length - 1}
                  onClick={() => api.setCurveDag(index + 1)}
                >
                  <ChevronRight />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Nästa dag</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {bem30 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge variant="secondary" className="rounded-full px-3 py-1">
              Schemalagda medarbetare: {bemMin}–{bemMax} på plats
            </Badge>
          </div>
        ) : null}

        <div className="relative mt-6 flex h-56 items-end gap-px overflow-hidden rounded-xl bg-muted/40 px-2 pt-3">
          {slots.map((s, i: number) => (
            <Tooltip key={s.klockan}>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "relative flex h-full flex-1 items-end justify-center",
                    natt(s.klockan) && "bg-secondary/60",
                  )}
                >
                  <i
                    className="absolute bottom-0 w-full rounded-t-[3px] bg-[var(--graf-dim)]"
                    style={{ height: `${(s.dimensionerat / skala) * 92}%` }}
                  />
                  <i
                    className="absolute bottom-0 w-full rounded-t-[3px] bg-sky-400/80"
                    style={{ height: `${(s.rabehov / skala) * 92}%` }}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent>
                {s.klockan}: rått {h1(s.rabehov)}, dimensionerat {s.dimensionerat}
                {bem30 ? `, schemalagda ${bem30[i]}` : ""}
              </TooltipContent>
            </Tooltip>
          ))}
          {punkter ? (
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <polyline points={punkter} fill="none" stroke="var(--color-deep, var(--djup-mork))" strokeWidth="1.2" />
            </svg>
          ) : null}
        </div>

        <div className="mt-2 flex justify-between text-[11px] font-semibold text-muted-foreground tabular-nums">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>

        <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-border pt-4">
          <Forklaring farg="rgb(56 168 231 / 0.8)" text="Rått behov (decimaler)" />
          <Forklaring farg="var(--graf-dim)" text="Dimensionerat (uppåt, minst nattgolv)" />
          {bem30 ? <Forklaring farg="var(--djup-mork)" text="Schemalagda medarbetare" linje /> : null}
          <Forklaring farg="var(--graf-band)" text="Natt 22–06" />
        </div>
      </Card>
    </div>
  );
}
