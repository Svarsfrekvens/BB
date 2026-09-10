import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Check, CircleAlert, FileText, ListChecks } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function ton(status: string) {
  if (/pass/i.test(status)) return { bg: "var(--ok-mjuk)", fg: "var(--ok)", ikon: <Check className="size-3.5" /> };
  if (/åtgärd/i.test(status)) return { bg: "var(--fara-mjuk)", fg: "var(--fara)", ikon: <AlertTriangle className="size-3.5" /> };
  return { bg: "var(--varn-mjuk)", fg: "var(--varn)", ikon: <CircleAlert className="size-3.5" /> };
}

export function Atgarder({ d, state, api }: VyProps) {
  const lista = state?.kontroller ?? null;
  const schemaVarningar = api.schemaVarningar();
  const schemaForandringar = api.schemaForandringar();
  const beslut = api.vikarieBeslut();

  const Vikarier = beslut.length ? (
    <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 pt-6 pb-4">
        <div>
          <Eyebrow>Vikariepass</Eyebrow>
          <h2 className="mt-1 text-lg font-bold text-deep">Beslut om de öppna passen</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Varje pass som behålls är en åtgärd: tillsätt vikarie.
          </p>
        </div>
        <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
          {beslut.filter((b) => b.behovs).length} att tillsätta
        </Badge>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-border/60 bg-muted/40 text-left">
              {["Datum", "Pass", "Beslut", "Skäl"].map((c) => (
                <th key={c} className="px-6 py-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {beslut.map((b) => (
              <tr key={b.id} className={b.behovs ? "border-b border-border/50 bg-warning-soft/40" : "border-b border-border/50"}>
                <td className="px-6 py-3 whitespace-nowrap text-deep tabular-nums">{b.datum}</td>
                <td className="px-6 py-3 whitespace-nowrap text-deep tabular-nums">
                  {b.start}–{b.slut} · {api.h1(b.timmar)}
                </td>
                <td className="px-6 py-3">
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold whitespace-nowrap"
                    style={{
                      background: b.behovs ? "var(--varn-mjuk)" : "var(--ok-mjuk)",
                      color: b.behovs ? "var(--varn)" : "var(--ok)",
                    }}
                  >
                    {b.behovs ? <CircleAlert className="size-3.5" /> : <Check className="size-3.5" />}
                    {b.behovs ? "Tillsätt vikarie" : "Tas bort"}
                  </span>
                </td>
                <td className="px-6 py-3 text-muted-foreground">
                  {b.behovs
                    ? `Fyller ett gap i bemanningen kl. ${b.start}–${b.slut}`
                    : "Behovet täcks av ordinarie personal"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  ) : null;

  const Schema = schemaVarningar.length || schemaForandringar.length ? (
    <Card className="gap-0 rounded-2xl p-6 shadow-lift">
      <Eyebrow>Schemaoptimering</Eyebrow>
      <h2 className="mt-1 text-lg font-bold text-deep">Ändringar och varningar</h2>
      <div className="mt-4 space-y-2 text-sm">
        {schemaForandringar.map((r, i) => (
          <p key={`f-${i}`} className="text-deep">{r.text}</p>
        ))}
        {schemaVarningar.map((r, i) => (
          <p key={`v-${i}`} className="text-warning">{r.text}</p>
        ))}
      </div>
    </Card>
  ) : null;

  if (!d || !lista) {
    return (
      <div className="space-y-4">
        {Vikarier}
        {Schema}
        <Card className="rounded-2xl p-8 text-center shadow-lift">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-xs font-bold text-deep">
            XLS
          </div>
          <h2 className="mt-4 text-xl font-bold text-deep">Modellens kontroller saknas</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
            Filen saknar bladet Kontroller – läs in en fil med modellbladen, så syns verksamhetens kontroller här.
          </p>
          <Button className="mt-6" onClick={() => api.valjFil()}>
            <FileText /> Välj Excel-fil
          </Button>
        </Card>
      </div>
    );
  }

  const cell = (v: unknown) => {
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : api.h1(v);
    return v == null ? "" : String(v);
  };
  const behover = lista.filter((r) => !/^pass$/i.test(String(r.status)));
  const modellstatus = api.ber("Modellstatus");
  const statusText = modellstatus
    ? String(modellstatus)
    : behover.length
      ? behover.length + " att åtgärda"
      : "Allt godkänt";

  return (
    <div className="space-y-4">
      <Card
        className="gap-0 rounded-2xl p-6 shadow-lift md:p-8"
        style={{ borderLeftWidth: 4, borderLeftColor: behover.length ? "var(--varn)" : "var(--ok)" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-deep">
              <ListChecks className="size-5" />
            </span>
            <div>
              <Eyebrow>Modellens kontroller</Eyebrow>
              <h1 className="mt-0.5 text-2xl font-extrabold tracking-tight text-deep md:text-3xl">
                Vad verksamheten behöver titta på
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                Varje rad är en kontroll ur filen. Börja med raderna som är gula eller röda – de påverkar hur säkra
                talen är.
              </p>
            </div>
          </div>
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold"
            style={{
              background: behover.length ? "var(--varn-mjuk)" : "var(--ok-mjuk)",
              color: behover.length ? "var(--varn)" : "var(--ok)",
            }}
          >
            {behover.length ? <CircleAlert className="size-3.5" /> : <Check className="size-3.5" />}
            {statusText}
          </span>
        </div>
      </Card>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="flex items-center justify-between px-6 pt-6 pb-4">
          <Eyebrow>Alla kontroller</Eyebrow>
          <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
            {lista.length} rader
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-y border-border/60 bg-muted/40 text-left">
                {["Kontroll", "Utfall", "Förväntat", "Status", "Kommentar"].map((c) => (
                  <th key={c} className="px-6 py-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lista.map((r, i) => {
                const t = ton(String(r.status));
                return (
                  <tr key={i} className="border-b border-border/50 transition-colors hover:bg-muted/40">
                    <td className="px-6 py-3 font-semibold text-deep">{r.kontroll}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-deep tabular-nums">{cell(r.utfall)}</td>
                    <td className="px-6 py-3 whitespace-nowrap text-muted-foreground tabular-nums">
                      {cell(r.forvantat)}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold whitespace-nowrap"
                        style={{ background: t.bg, color: t.fg }}
                      >
                        {t.ikon}
                        {String(r.status)}
                      </span>
                    </td>
                    <td className="max-w-xs px-6 py-3 text-xs leading-snug text-muted-foreground/80">
                      {r.atgard || ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {Vikarier}
      {Schema}
    </div>
  );
}
