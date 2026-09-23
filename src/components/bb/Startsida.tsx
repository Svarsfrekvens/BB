import { useRef } from "react";
import { ArrowRight, CalendarClock, HeartHandshake, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function Startsida({
  onKundFil,
  onSchemaFil,
  onFortsatt,
}: {
  onKundFil: (fil: File) => void;
  onSchemaFil: (fil: File) => void;
  onFortsatt: () => void;
}) {
  const kundFil = useRef<HTMLInputElement>(null);
  const schemaFil = useRef<HTMLInputElement>(null);

  const lasFil = (fil: File | undefined, fn: (f: File) => void) => {
    if (fil) window.setTimeout(() => fn(fil), 0);
  };

  const kort = [
    {
      id: "kund",
      ikon: HeartHandshake,
      rubrik: "Ladda upp kundbehov",
      text: "Sekoia-export",
      knapp: "Ladda upp",
      aria: "Ladda upp kundbehov",
      stark: true,
      onClick: () => kundFil.current?.click(),
    },
    {
      id: "schema",
      ikon: CalendarClock,
      rubrik: "Ladda upp schema",
      text: "Medarbetare och aktuellt schema",
      knapp: "Ladda upp",
      aria: "Ladda upp schema",
      stark: false,
      onClick: () => schemaFil.current?.click(),
    },
    {
      id: "fortsatt",
      ikon: UserRound,
      rubrik: "Fortsätt arbeta",
      text: "Återuppta nästa steg i flödet",
      knapp: "Fortsätt",
      aria: "Fortsätt till nästa steg",
      stark: false,
      onClick: onFortsatt,
    },
  ] as const;

  return (
    <div className="relative mx-auto flex min-h-[80vh] max-w-[1180px] flex-col justify-center px-4 py-20">
      <div
        className="pointer-events-none absolute inset-x-0 top-8 h-64 bg-[radial-gradient(ellipse_at_top,rgba(0,70,145,0.08),transparent_62%)]"
        aria-hidden
      />
      <input
        ref={kundFil}
        type="file"
        accept=".xlsx,.xls"
        className="sr-only"
        aria-label="Välj kundbehov från Sekoia"
        onChange={(e) => {
          lasFil(e.currentTarget.files?.[0], onKundFil);
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
          lasFil(e.currentTarget.files?.[0], onSchemaFil);
          e.currentTarget.value = "";
        }}
      />

      <p className="relative text-[15px] font-medium tracking-wide text-muted-foreground">Välkommen till</p>
      <h1 className="relative mt-2 text-[40px] font-extrabold leading-[1.1] tracking-tight text-deep">Bemanningsbalans</h1>
      <h2 className="relative mt-12 text-[28px] font-extrabold tracking-tight text-deep">Vad vill du göra idag?</h2>

      <div className="relative mt-10 grid gap-6 md:grid-cols-3">
        {kort.map((k) => {
          const Ikon = k.ikon;
          return (
            <Card
              key={k.id}
              className={cn(
                "card-lift flex min-h-[300px] flex-col gap-5 rounded-[28px] p-9 text-left",
                k.stark
                  ? "border-transparent bg-gradient-to-b from-white to-primary-soft/40 shadow-lift-lg"
                  : "bg-white",
              )}
            >
              <span className="grid size-12 place-items-center rounded-2xl bg-primary-soft text-deep">
                <Ikon className="size-6" />
              </span>
              <h3 className="text-[20px] font-extrabold leading-snug text-deep">{k.rubrik}</h3>
              <p className="text-[15px] leading-relaxed text-muted-foreground">{k.text}</p>
              <Button
                size="lg"
                className="mt-auto h-12 rounded-2xl px-6 text-[16px] shadow-lift"
                aria-label={k.aria}
                onClick={k.onClick}
              >
                {k.knapp}
                {k.id === "fortsatt" ? <ArrowRight /> : null}
              </Button>
            </Card>
          );
        })}
      </div>

      <p className="relative mt-12 text-center text-[14px] text-muted-foreground/75">
        Du kan ladda upp kundbehov, schema eller båda.
      </p>
    </div>
  );
}
