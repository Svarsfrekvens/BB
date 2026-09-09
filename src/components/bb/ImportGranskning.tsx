import { useSyncExternalStore } from "react";
import { CheckCircle2, AlertTriangle, XCircle, FileSpreadsheet } from "lucide-react";
import { bbVy } from "@/lib/bb/vy";
import { bbSkal } from "@/lib/bb/skal";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

/** Granskning före sparande: inget skrivs in innan du godkänner. */
export function ImportGranskning() {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  const api = v.api;
  const p = v.pending;
  const meta = v.pendingMeta;
  if (!api || !p || !meta) return null;

  const blockerad = !!p.blockera;
  // Sant när verksamheten redan har data som skrivs över.
  const befintliga = v.state ? v.state["rows"] : null;
  const ersatter = Array.isArray(befintliga) && befintliga.length > 0;
  const block: string[] = (p.varningar || []).filter((x: string) => x.startsWith("BLOCKERAT"));
  const varn: string[] = (p.varningar || []).filter((x: string) => !x.startsWith("BLOCKERAT"));
  const avvisade = (p.avvisade || []).slice(0, 50);

  const tal: [string, number | string][] = [
    ["Lästa rader", p.lastaRader],
    ["Godkända rader", p.godkandaRader],
    ["Avvisade rader", p.avvisadeRader],
    ["Kunder", p.antalKunder],
    ["Gemensamma", p.antalGemensamma],
    ["Fasta", p.antalFasta],
    ["Flyttbara", p.antalFlyttbara],
    ["Dubbelbemannade", p.antalDubbelbemannade],
  ];

  const status = blockerad
    ? { ikon: XCircle, text: "Importen blockeras", kls: "border-primary/40 bg-primary-soft text-primary" }
    : varn.length
      ? { ikon: AlertTriangle, text: "Varningar att titta på", kls: "border-[var(--warning)]/40 bg-[var(--warning-soft)] text-[var(--warning)]" }
      : { ikon: CheckCircle2, text: "Klar att läsa in", kls: "border-[var(--success)]/40 bg-[var(--success-soft)] text-[var(--success)]" };
  const StatusIkon = status.ikon;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) api.avbrytImport(); }}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto rounded-2xl p-7">
        <DialogHeader>
          <div className="text-[11px] font-bold tracking-widest text-primary uppercase">
            Granska innan något sparas
          </div>
          <DialogTitle className="flex items-center gap-2 text-2xl font-extrabold tracking-tight text-deep">
            <FileSpreadsheet className="size-6 text-muted-foreground" /> {meta.fileName}
          </DialogTitle>
          <DialogDescription className="text-sm leading-relaxed">
            Flik <strong className="font-semibold text-deep">{meta.sheet}</strong> · rubrikrad {meta.headerRow} · period{" "}
            {p.from}–{p.to} ({p.days} dagar). Bara modellens egna fält läses in.
          </DialogDescription>
        </DialogHeader>

        <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-bold ${status.kls}`}>
          <StatusIkon className="size-4" /> {status.text}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tal.map(([lab, varde]) => (
            <div key={lab} className="rounded-xl border border-border bg-background p-3">
              <div className="text-[11px] font-semibold text-muted-foreground">{lab}</div>
              <div className="mt-0.5 text-xl font-extrabold text-deep tabular-nums">{varde}</div>
            </div>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-[11px] font-bold tracking-wide text-muted-foreground uppercase">
                <tr>
                  <th className="px-3 py-2">Timmar per kund ({p.days} dagar)</th>
                  <th className="px-3 py-2 text-right">Insatser</th>
                  <th className="px-3 py-2 text-right">Kundbehov</th>
                </tr>
              </thead>
              <tbody>
                {(p.timmarPerKund || []).map((k) => (
                  <tr key={k.kund} className="border-t border-border/60">
                    <td className="px-3 py-2 font-semibold text-deep">{k.kund}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{k.insatser}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{api.h1(k.kundbehovH)} h</td>
                  </tr>
                ))}
                <tr className="border-t border-border bg-muted/40 font-bold text-deep">
                  <td className="px-3 py-2">Totalt</td>
                  <td className="px-3 py-2 text-right tabular-nums">{p.godkandaRader}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{api.h1(p.kundbehovH)} h</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3">
            <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm leading-relaxed text-deep">
              <strong className="font-bold">Hela perioden {p.from}–{p.to}:</strong> kundbehov{" "}
              <span className="tabular-nums">{api.h1(p.kundbehovH)} h</span> · personalbehov inklusive dubbelbemanning{" "}
              <span className="tabular-nums">{api.h1(p.personalbehovH)} h</span>.
              {p.first28 && (
                <>
                  <br />
                  <strong className="font-bold">Bemanningsplan dag 1–28:</strong> {p.first28.count} insatser · kundbehov{" "}
                  <span className="tabular-nums">{api.h1(p.first28.kundbehovH)} h</span> · personalbehov{" "}
                  <span className="tabular-nums">{api.h1(p.first28.personalbehovH)} h</span>.
                </>
              )}
            </div>
            {!!block.length && (
              <div className="rounded-xl border border-primary/40 bg-primary-soft p-3 text-sm text-primary">
                <strong className="flex items-center gap-1.5 font-bold">
                  <XCircle className="size-4" /> Blockerar import
                </strong>
                {block.map((b) => (
                  <div key={b} className="mt-1">
                    {b.replace("BLOCKERAT: ", "")}
                  </div>
                ))}
              </div>
            )}
            {!!varn.length && (
              <div className="rounded-xl border border-[var(--warning)]/40 bg-[var(--warning-soft)] p-3 text-sm text-[var(--warning)]">
                <strong className="flex items-center gap-1.5 font-bold">
                  <AlertTriangle className="size-4" /> Varningar
                </strong>
                {varn.map((w) => (
                  <div key={w} className="mt-1">
                    {w}
                  </div>
                ))}
              </div>
            )}
            {!!avvisade.length && (
              <div className="max-h-40 overflow-auto rounded-xl border border-border bg-background p-3 text-sm">
                <strong className="font-bold text-deep">Avvisade rader</strong>
                {avvisade.map((a, i: number) => (
                  <div key={i} className="mt-1 text-muted-foreground">
                    Rad {a.kallrad}: {a.orsak}
                  </div>
                ))}
                {p.avvisade.length > 50 && (
                  <div className="mt-1 text-muted-foreground">… och {p.avvisade.length - 50} till.</div>
                )}
              </div>
            )}
          </div>
        </div>

        {ersatter ? (
          <p className="flex items-start gap-2 rounded-xl border border-[var(--warning)]/40 bg-[var(--warning-soft)] px-3 py-2 text-sm text-[var(--warning)]">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>
              Den här verksamheten har redan inläst data. Läser du in filen ersätts den. Exportera först om du vill
              spara det du har nu.
            </span>
          </p>
        ) : null}

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => api.avbrytImport()}>
            Avbryt
          </Button>
          {ersatter ? (
            <Button variant="outline" onClick={() => bbSkal.actions.exportera?.()}>
              Exportera först
            </Button>
          ) : null}
          <Button disabled={blockerad} onClick={() => api.godkannImport()}>
            <CheckCircle2 /> {ersatter ? "Ersätt och läs in" : "Godkänn och läs in"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
