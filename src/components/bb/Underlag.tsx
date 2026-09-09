import { CheckCircle2, FileSpreadsheet, Sparkles, Trash2, Upload, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";

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

export function Underlag({ api }: VyProps) {
  const u = api.underlag();
  const schema = u.schema;
  const sekoia = u.sekoia;
  const klart = !!schema && !!sekoia;

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Steg 1 · Underlag</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Två filer ligger till grund för allt</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Personalschemat visar hur ni arbetar i dag. Kundfilen visar vad kunderna faktiskt behöver. Båda filerna sparas
          precis som de lästes in – förslaget räknas alltid fram på en kopia, så du kan alltid gå tillbaka till originalet.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Eyebrow>Personalschema</Eyebrow>
              <h3 className="mt-1 text-lg font-extrabold text-deep">Så arbetar personalen i dag</h3>
            </div>
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
              <Users className="size-5" />
            </span>
          </div>
          {schema ? (
            <>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge className="rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
                  <CheckCircle2 className="size-3" /> Inläst
                </Badge>
                <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
                  {schema.filnamn || schema.blad}
                </Badge>
              </div>
              <div className="mt-4">
                <Rad etikett="Medarbetare med schema" varde={String(schema.medarbetare)} />
                <Rad etikett="Vakanta schemarader" varde={String(schema.vakanta)} />
                <Rad etikett="Pass i schemarullen" varde={String(schema.pass)} />
                <Rad etikett="Veckor i rullen" varde={String(schema.veckor)} />
                <Rad etikett="Arbetad tid i rullen" varde={fmtH(schema.timmar)} />
                <Rad etikett="Sovande jour i rullen" varde={fmtH(schema.jour)} />
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => api.valjSchemaFil()}>
                  <Upload /> Byt fil
                </Button>
                <Button variant="ghost" onClick={() => api.rensaSchemaOriginal()}>
                  <Trash2 /> Ta bort
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                Ladda upp schemafilen ur Medvind. Appen läser namn, sysselsättningsgrad, vakanta rader och alla pass –
                även sovande jour över natten.
              </p>
              <Button className="mt-5 w-fit" onClick={() => api.valjSchemaFil()}>
                <Upload /> Välj schemafil
              </Button>
            </>
          )}
        </Card>

        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Eyebrow>Kundernas behov</Eyebrow>
              <h3 className="mt-1 text-lg font-extrabold text-deep">Vad kunderna behöver</h3>
            </div>
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
              <FileSpreadsheet className="size-5" />
            </span>
          </div>
          {sekoia ? (
            <>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge className="rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
                  <CheckCircle2 className="size-3" /> Inläst
                </Badge>
              </div>
              <div className="mt-4">
                <Rad etikett="Insatser" varde={String(sekoia.insatser)} />
                <Rad etikett="Kunder" varde={String(sekoia.kunder)} />
                <Rad etikett="Period i filen" varde={`${sekoia.from} – ${sekoia.to}`} />
                <Rad etikett="Tid hos kund" varde={fmtH(sekoia.timmar)} />
                <Rad etikett="Period som analyseras" varde={`${u.period.from} – ${u.period.to}`} />
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => api.valjFil()}>
                  <Upload /> Byt fil
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                Ladda upp rapporten med kundernas insatser. Appen läser tider, längd, kund och om insatsen är fast eller
                flyttbar.
              </p>
              <Button className="mt-5 w-fit" onClick={() => api.valjFil()}>
                <Upload /> Välj kundfil
              </Button>
            </>
          )}
        </Card>
      </div>

      <Card className="gap-0 rounded-2xl p-7 shadow-lift">
        <Eyebrow>Förutsättningar i verksamheten</Eyebrow>
        <h3 className="mt-1 text-lg font-extrabold text-deep">Det här tar appen hänsyn till</h3>
        <div className="mt-4 grid gap-x-8 sm:grid-cols-2">
          {u.villkor.map((v) => (
            <Rad key={v.regel} etikett={v.regel} varde={v.varde} />
          ))}
        </div>
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-4 rounded-2xl p-7 shadow-lift">
        <div>
          <strong className="block text-base font-extrabold text-deep">
            {klart ? "Underlaget är klart" : "Båda filerna behövs"}
          </strong>
          <span className="mt-1 block text-sm text-muted-foreground">
            {klart
              ? u.balans
                ? `Förslag finns: ${u.balans.flyttade} insatser har fått nya tider.`
                : "Nu kan appen jämföra dagens schema med kundernas behov."
              : "Ladda upp både personalschemat och kundfilen för att komma vidare."}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {u.balans ? (
            <Button variant="outline" onClick={() => api.aterstallBalans()}>
              Tillbaka till originaldata
            </Button>
          ) : null}
          <Button disabled={!klart} onClick={() => api.skapaBalans()}>
            <Sparkles /> Skapa bemanningsbalans
          </Button>
        </div>
      </Card>
    </div>
  );
}
