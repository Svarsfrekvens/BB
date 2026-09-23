import { useRef, useSyncExternalStore } from "react";
import { ArrowRight, CalendarClock, CheckCircle2, HeartHandshake, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { bbVy, fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { sattStartlage } from "@/lib/bb/startlage";

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
  const rawOrg = v.verks.find((x) => x.id === v.aktivVerks)?.org || "";
  const orgNamn = rawOrg === "Ny verksamhet" ? "" : rawOrg;
  const kundFil = useRef<HTMLInputElement>(null);
  const schemaFil = useRef<HTMLInputElement>(null);

  const lasFil = (fil: File | undefined, fn: (f: File) => void) => {
    if (fil) window.setTimeout(() => fn(fil), 0);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <input
        ref={kundFil}
        type="file"
        accept=".xlsx,.xls"
        className="sr-only"
        aria-label="Välj kundbehov från Sekoia"
        onChange={(e) => {
          lasFil(e.currentTarget.files?.[0], api.hanteraFil);
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
          lasFil(e.currentTarget.files?.[0], api.hanteraSchemaFil);
          e.currentTarget.value = "";
        }}
      />

      <div className="text-center">
        <h2 className="text-[36px] font-extrabold tracking-tight text-deep">Ladda upp underlag</h2>
        <p className="mx-auto mt-3 max-w-xl text-base leading-relaxed text-muted-foreground">
          Starta en ny period med kundbehov och aktuellt schema.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          className="card-lift gap-5 rounded-[28px] p-10"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            lasFil(e.dataTransfer.files?.[0], api.hanteraFil);
          }}
        >
          <span className="grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
            {sekoia ? <CheckCircle2 className="size-7 text-ok" /> : <HeartHandshake className="size-7" />}
          </span>
          <h3 className="text-[20px] font-extrabold text-deep">Kundbehov</h3>
          <p className="text-base text-muted-foreground">Sekoia-export</p>
          {sekoia ? (
            <p className="text-sm font-semibold text-deep">
              {sekoia.insatser} insatser · {fmtH(sekoia.timmar)} · {sekoia.kunder} kunder
            </p>
          ) : null}
          <Button size="lg" className="mt-2 h-12 rounded-2xl" onClick={() => kundFil.current?.click()}>
            <Upload /> {sekoia ? "Byt kundbehov" : "Ladda upp kundbehov"}
          </Button>
        </Card>

        <Card
          className="card-lift gap-5 rounded-[28px] p-10"
          onDragOver={(e) => !sekoia || e.preventDefault()}
          onDrop={(e) => {
            if (!sekoia) return;
            e.preventDefault();
            lasFil(e.dataTransfer.files?.[0], api.hanteraSchemaFil);
          }}
        >
          <span className="grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
            {schema ? <CheckCircle2 className="size-7 text-ok" /> : <CalendarClock className="size-7" />}
          </span>
          <h3 className="text-[20px] font-extrabold text-deep">Medarbetare & schema</h3>
          <p className="text-base text-muted-foreground">Aktuellt personalschema</p>
          {schema ? (
            <p className="text-sm font-semibold text-deep">
              {schema.medarbetare} medarbetare · {schema.pass} pass · {fmtH(schema.timmar)}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {sekoia ? "Ladda upp Medvind-exporten." : "Läs in kundbehovet först."}
            </p>
          )}
          <Button
            size="lg"
            className="mt-2 h-12 rounded-2xl"
            disabled={!sekoia}
            onClick={() => schemaFil.current?.click()}
          >
            <Upload /> {schema ? "Byt schema" : "Ladda upp schema"}
          </Button>
        </Card>
      </div>

      <div className="mx-auto max-w-md space-y-2">
        <label htmlFor="bb-org" className="text-sm font-bold text-deep">
          Verksamhetens namn
        </label>
        <input
          id="bb-org"
          value={orgNamn}
          placeholder="t.ex. Galaxen"
          onChange={(e) => api.setOrg(e.target.value)}
          className="h-11 w-full rounded-xl border border-input bg-card px-3 text-base font-semibold text-deep outline-none focus-visible:border-ring"
        />
      </div>

      {filerKlara ? (
        <div className="flex justify-center">
          <Button
            size="lg"
            className="h-14 rounded-2xl px-10 text-base shadow-lift"
            onClick={() => {
              sattStartlage("app");
              api.setTab(u.godkand.schema ? "planering" : "medarbetare");
            }}
          >
            {u.godkand.schema ? "Fortsätt till planering" : "Fortsätt till medarbetare"} <ArrowRight />
          </Button>
        </div>
      ) : null}

      {sekoia && !u.godkand.kund ? (
        <p className="text-center text-sm text-muted-foreground">
          Kundfilen väntar på godkännande i granskningsdialogen.
        </p>
      ) : null}
    </div>
  );
}
