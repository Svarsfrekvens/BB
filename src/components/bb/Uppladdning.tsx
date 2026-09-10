import { useRef, useSyncExternalStore } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  HeartHandshake,
  Info,
  LayoutDashboard,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { bbVy, fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { Medarbetare } from "./Medarbetare";

/** Ett steg i underlagslistan: ikon, rubrik, status och en filknapp med släppyta. */
function Steg({
  ikon: Ikon,
  klar,
  titel,
  kalla,
  status,
  knapp,
  last,
  onKlick,
  onFil,
}: {
  ikon: LucideIcon;
  klar: boolean;
  titel: string;
  kalla: string;
  status?: string | undefined;
  knapp?: string;
  last?: boolean;
  onKlick?: () => void;
  onFil?: (f: File) => void;
}) {
  const lasIn = (fil: File) => {
    window.setTimeout(() => onFil?.(fil), 0);
  };
  return (
    <div
      onDragOver={(e) => !last && e.preventDefault()}
      onDrop={(e) => {
        if (last) return;
        e.preventDefault();
        const f = e.dataTransfer.files?.[0];
        if (f && onFil) lasIn(f);
      }}
      className={`flex flex-wrap items-center gap-5 border-b border-border px-6 py-7 last:border-0 ${last ? "opacity-60" : ""}`}
    >
      <span
        className={`grid size-12 shrink-0 place-items-center rounded-2xl ${
          klar ? "bg-success-soft text-success" : "bg-muted text-deep"
        }`}
      >
        {klar ? <CheckCircle2 className="size-6" /> : <Ikon className="size-6" />}
      </span>
      <div className="min-w-[200px] flex-1">
        <strong className="block text-base font-extrabold text-deep">{titel}</strong>
        <span className="block text-[13px] text-muted-foreground">{kalla}</span>
        {status ? (
          <span className="mt-2 inline-block rounded-lg bg-success-soft px-3 py-1.5 text-[13px] font-semibold text-success">
            {status}
          </span>
        ) : null}
      </div>
      {last || !knapp ? null : (
        <Button variant={klar ? "outline" : "default"} size="sm" onClick={onKlick}>
          <Upload /> {knapp}
        </Button>
      )}
    </div>
  );
}

/** Underlag: två tydliga vägar – starta nytt eller fortsätt med sparat arbete. */
export function Uppladdning(props: VyProps) {
  const { api } = props;
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  const u = api.underlag();
  const sekoia = u.sekoia;
  const schema = u.schema;
  const filerKlara = !!sekoia && !!schema;
  const klart = filerKlara && u.godkand.allt;
  const harBalans = api.harBalans();
  const sparat = api.sparadInfo();
  const rawOrg = v.verks.find((x) => x.id === v.aktivVerks)?.org || "";
  const orgNamn = rawOrg === "Ny verksamhet" ? "" : rawOrg;
  const org = orgNamn || "din verksamhet";
  const kundFil = useRef<HTMLInputElement>(null);
  const schemaFil = useRef<HTMLInputElement>(null);
  const kundRader = api.arbetsRader();
  const kunder = api.gfpKunder().map((namn) => {
    const rader = kundRader.filter((r) => String(r.kund) === namn);
    return { namn, insatser: rader.length, timmar: rader.reduce((s, r) => s + (Number(r.minuter) || 0), 0) / 60 };
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <input
        ref={kundFil}
        type="file"
        accept=".xlsx,.xls"
        className="sr-only"
        aria-label="Välj kundbehov från Sekoia"
        onChange={(e) => {
          const fil = e.currentTarget.files?.[0];
          if (fil) window.setTimeout(() => api.hanteraFil(fil), 0);
          e.currentTarget.value = "";
        }}
      />
      <input
        ref={schemaFil}
        type="file"
        accept=".xlsx,.xls"
        className="sr-only"
        aria-label="Välj personalschema från Medvind"
        onChange={(e) => {
          const fil = e.currentTarget.files?.[0];
          if (fil) window.setTimeout(() => api.hanteraSchemaFil(fil), 0);
          e.currentTarget.value = "";
        }}
      />
      <div className="text-center">
        <span className="inline-flex items-center gap-2 rounded-full bg-success-soft px-3 py-1 text-[13px] font-semibold text-success">
          <HeartHandshake className="size-4" /> {org}
        </span>
        <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-deep sm:text-4xl">
          {klart ? "Underlagen är klara" : "Börja här"}
        </h2>
        <p className="mx-auto mt-2 max-w-xl text-base text-muted-foreground">
          Ladda upp kundernas behov och personalschemat. Granska och godkänn båda innan bemanningsbalansen skapas.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ---------- Vänster: starta nytt ---------- */}
        <div className="space-y-4">
          <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
            <div className="border-b border-border bg-muted/50 px-6 py-4">
              <strong className="block text-base font-extrabold text-deep">Starta nytt</strong>
              <span className="text-[13px] text-muted-foreground">Kundernas behov först, sedan nuvarande schema.</span>
            </div>

            <Steg
              ikon={HeartHandshake}
              klar={!!sekoia}
              titel="1. Ladda upp kundernas behov"
              kalla="Sekoia-export, bladet Rapport"
              status={
                sekoia
                  ? `${sekoia.insatser} insatser · ${fmtH(sekoia.timmar)} · ${sekoia.kunder} kunder · ${sekoia.from} – ${sekoia.to}`
                  : undefined
              }
              knapp={sekoia ? "Byt fil" : "Välj fil"}
              onKlick={() => kundFil.current?.click()}
              onFil={(f) => api.hanteraFil(f)}
            />

            {sekoia ? (
              <div className="bb-steg-in animated fadeInUp">
                <Steg
                  ikon={CalendarClock}
                  klar={!!schema}
                  titel="2. Läs in nuvarande schema"
                  kalla="Medvind-export – blir läget före"
                  status={
                    schema
                      ? `${schema.medarbetare} medarbetare · ${schema.vikarier} vikarier · ${schema.pass} pass · ${fmtH(schema.timmar)}`
                      : undefined
                  }
                  knapp={schema ? "Byt fil" : "Välj fil"}
                  onKlick={() => schemaFil.current?.click()}
                  onFil={(f) => api.hanteraSchemaFil(f)}
                />
              </div>
            ) : (
              <Steg
                ikon={CalendarClock}
                klar={false}
                titel="2. Läs in nuvarande schema"
                kalla="Dyker upp så fort kundernas behov är inläst."
                last
              />
            )}

            {filerKlara ? (
              <div className="bb-steg-in animated fadeInUp space-y-4 px-6 py-7">
                <Button size="lg" className="w-full" disabled={!u.godkand.allt} onClick={() => api.setTab("motor")}>
                  <Sparkles /> {harBalans ? "Skapa om bemanningsbalans" : "Skapa bemanningsbalans"}
                </Button>

              </div>
            ) : null}
          </Card>

          <Card className="gap-2 rounded-2xl p-6 shadow-lift">
            <label htmlFor="bb-org" className="text-sm font-bold text-deep">
              Verksamhetens namn
            </label>
            <input
              id="bb-org"
              value={orgNamn}
              placeholder="t.ex. Galaxen"
              onChange={(e) => api.setOrg(e.target.value)}
              className="h-11 w-full rounded-xl border border-input bg-card px-3 text-base font-semibold text-deep outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
            />
            <span className="text-[13px] text-muted-foreground">Namnet visas i sidhuvudet och i rapporterna.</span>
          </Card>
        </div>

        {/* ---------- Höger: fortsätt med befintlig data ---------- */}
        <Card className={`gap-4 rounded-2xl p-6 shadow-lift ${sparat ? "" : "opacity-70"}`}>
          <span
            className={`grid size-12 place-items-center rounded-2xl ${
              sparat ? "bg-success-soft text-success" : "bg-muted text-deep"
            }`}
          >
            {sparat ? <LayoutDashboard className="size-6" /> : <Info className="size-6" />}
          </span>
          <div>
            <strong className="block text-base font-extrabold text-deep">Fortsätt med befintlig data</strong>
            <span className="text-[13px] text-muted-foreground">
              {sparat ? "Ditt arbete finns kvar sedan sist." : "Här visas ditt sparade arbete."}
            </span>
          </div>

          {sparat ? (
            <>
              <dl className="grid gap-2 rounded-xl bg-muted/60 p-4 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Period</dt>
                  <dd className="font-semibold text-deep">{sparat.period}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Kundinsatser</dt>
                  <dd className="font-semibold text-deep">
                    {sparat.insatser} st · {sparat.kunder} kunder
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Schema</dt>
                  <dd className="font-semibold text-deep">
                    {sparat.medarbetare} medarbetare · {sparat.pass} pass
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Bemanningsbalans</dt>
                  <dd className="font-semibold text-deep">{sparat.balans ? "Skapad" : "Inte skapad ännu"}</dd>
                </div>
                {sparat.uppdaterad ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Senast uppdaterad</dt>
                    <dd className="font-semibold text-deep">
                      {new Date(sparat.uppdaterad).toLocaleString("sv-SE", { dateStyle: "short", timeStyle: "short" })}
                    </dd>
                  </div>
                ) : null}
              </dl>

              <div className="flex flex-wrap gap-2">
                <Button disabled={!sparat.balans} onClick={() => api.setTab("foreefter")}>
                  Öppna resultat <ArrowRight />
                </Button>
                <Button variant="outline" onClick={() => api.setTab("kundbehov")}>
                  Ändra kundbehov
                </Button>
                <Button variant="outline" onClick={() => api.setTab("schemaforslag")}>
                  Justera schema
                </Button>
                <Button
                  variant="outline"
                  className="border-destructive text-destructive"
                  onClick={() => {
                    if (window.confirm("Rensa underlaget för den här verksamheten?")) api.rensaUnderlag();
                  }}
                >
                  <Trash2 /> Rensa
                </Button>
              </div>
            </>
          ) : (
            <p className="rounded-xl bg-muted/60 p-4 text-sm text-muted-foreground">
              Arbetet sparas i den här webbläsaren, så du kan gå ifrån appen och komma tillbaka. I en kommande version
              sparas det centralt så att du kommer åt det från flera enheter.
            </p>
          )}
        </Card>
      </div>

      {sekoia && !u.godkand.kund ? (
        <section className="space-y-4" aria-labelledby="granska-kunder">
          <div className="text-center">
            <div className="text-xs font-bold tracking-widest text-primary uppercase">Steg 2</div>
            <h3 id="granska-kunder" className="mt-1 text-2xl font-extrabold text-deep">Granska kundunderlaget</h3>
            <p className="mt-1 text-sm text-muted-foreground">Kontrollera att alla kunder och deras insatser har kommit med.</p>
          </div>
          <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
            <div className="max-h-96 overflow-y-auto divide-y divide-border">
              {kunder.map((kund, i) => (
                <div key={kund.namn} className="grid grid-cols-[3rem_1fr_auto] items-center gap-3 px-5 py-4">
                  <span className="grid size-8 place-items-center rounded-full bg-primary-soft text-xs font-extrabold text-primary">{i + 1}</span>
                  <div><strong className="block text-sm text-deep">{kund.namn}</strong><span className="text-xs text-muted-foreground">{kund.insatser} insatser</span></div>
                  <strong className="text-sm tabular-nums text-deep">{fmtH(kund.timmar)}</strong>
                </div>
              ))}
            </div>
          </Card>
          <Card className="flex flex-wrap items-center justify-between gap-4 rounded-2xl p-6 shadow-lift">
            <div><strong className="block text-base font-extrabold text-deep">Finns alla kunder med?</strong><span className="text-sm text-muted-foreground">Godkänn när du har granskat listan.</span></div>
            <Button size="lg" onClick={() => api.godkannKund()}><CheckCircle2 /> Godkänn kundunderlaget</Button>
          </Card>
        </section>
      ) : null}

      {schema && !u.godkand.schema ? (
        <section className="space-y-4" aria-labelledby="granska-schema">
          <div className="text-center">
            <div className="text-xs font-bold tracking-widest text-primary uppercase">Steg 3</div>
            <h3 id="granska-schema" className="mt-1 text-2xl font-extrabold text-deep">Granska personalschemat</h3>
            <p className="mt-1 text-sm text-muted-foreground">Kontrollera sysselsättningsgrad, nattbehörighet, jour och passprofil.</p>
          </div>
          <div className="max-h-[38rem] overflow-y-auto rounded-2xl border border-border bg-background p-1 shadow-lift">
            <Medarbetare {...props} />
          </div>
          <Card className="flex flex-wrap items-center justify-between gap-4 rounded-2xl p-6 shadow-lift">
            <div><strong className="block text-base font-extrabold text-deep">Stämmer uppgifterna?</strong><span className="text-sm text-muted-foreground">Godkänn när du har granskat hela listan.</span></div>
            <Button size="lg" onClick={() => api.godkannSchema()}><CheckCircle2 /> Godkänn personalschemat</Button>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
