import { ArrowRight, CheckCircle2, Trash2, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { Slappyta } from "./Slappyta";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Rad({ etikett, varde }: { etikett: string; varde: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-0">
      <span className="text-sm text-muted-foreground">{etikett}</span>
      <strong className="text-sm font-bold tabular-nums text-deep">{varde}</strong>
    </div>
  );
}

/** Steg 3: ladda upp det befintliga personalschemat – appens FÖRE-läge. */
export function SchemaFil({ api }: VyProps) {
  const u = api.underlag();
  const schema = u.schema;

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Steg 3 · Schema</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Ladda upp befintligt schema</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Det uppladdade schemat är alltid utgångsläget – appen hittar inte på något nuläge. Filen sparas precis som den
          lästes in, och förslaget räknas fram på en kopia.
        </p>
        {!u.sekoia ? (
          <p className="mt-3 text-sm font-semibold text-[var(--warning)]">Kundgruppen måste laddas upp först.</p>
        ) : null}
      </Card>

      <Card className="gap-0 rounded-2xl p-7 shadow-lift">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Eyebrow>2 · Schema</Eyebrow>
            <h3 className="mt-1 text-lg font-extrabold text-deep">Så arbetar personalen i dag</h3>
          </div>
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <Users className="size-5" />
          </span>
        </div>

        {schema ? (
          <>
            <Badge className="mt-4 w-fit rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
              <CheckCircle2 className="size-3" /> Inläst · {schema.medarbetare} medarbetare · {fmtH(schema.timmar)}{" "}
              schematimmar
            </Badge>
            <div className="mt-4">
              <Rad etikett="Filnamn" varde={schema.filnamn || schema.blad} />
              <Rad etikett="Medarbetare med schema" varde={String(schema.medarbetare)} />
              <Rad etikett="Vakanta schemarader" varde={String(schema.vakanta)} />
              <Rad etikett="Pass i schemarullen" varde={String(schema.pass)} />
              <Rad etikett="Veckor i rullen" varde={String(schema.veckor)} />
              <Rad etikett="Arbetad tid i rullen" varde={fmtH(schema.timmar)} />
              <Rad etikett="Sovande jour i rullen" varde={fmtH(schema.jour)} />
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => api.valjSchemaFil()}>
                Byt fil
              </Button>
              <Button variant="ghost" onClick={() => api.rensaSchemaOriginal()}>
                <Trash2 /> Ta bort
              </Button>
              <Button onClick={() => api.setTab("medarbetare")}>
                Nästa: medarbetare <ArrowRight />
              </Button>
            </div>
          </>
        ) : (
          <Slappyta
            text="Släpp schemafilen här"
            hjalp="Excel (.xlsx) från Medvind – namn, sysselsättningsgrad, vakanta rader och alla pass inklusive sovande jour."
            onFil={(f) => api.hanteraSchemaFil(f)}
            onValj={() => api.valjSchemaFil()}
          />
        )}
      </Card>
    </div>
  );
}
