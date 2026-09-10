import { Fragment, useState } from "react";
import { ArrowRight, ChevronDown, ChevronRight, Info, Plus, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import type { VyProps } from "@/lib/bb/vy";
import { TomtLage } from "./Tomt";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

const PASSPROFIL = [
  { v: "blandat", t: "Blandat" },
  { v: "dag", t: "Endast dag" },
  { v: "kvall", t: "Endast kväll" },
  { v: "natt", t: "Ständig natt" },
];
const HELG = [
  { v: "varannan", t: "Varannan helg" },
  { v: "vartredje", t: "Var tredje helg" },
  { v: "alla", t: "Alla helger" },
  { v: "inga", t: "Inga helger" },
];
const FRANVARO = [
  { v: "ingen", t: "Ingen" },
  { v: "ledig1v", t: "Ledig 1 v/mån" },
  { v: "arbetar2v", t: "Arbetar 2 v/mån" },
  { v: "semester", t: "Semester del av period" },
];
const ANSTALLNING = [
  { v: "manad", t: "Månadsanställd" },
  { v: "timme", t: "Timavlönad" },
];

/** En liten select som sparar direkt när värdet ändras. */
function Val({
  varde,
  val,
  onValj,
  bred,
}: {
  varde: string;
  val: { v: string; t: string }[];
  onValj: (v: string) => void;
  bred?: boolean;
}) {
  return (
    <select
      value={varde}
      onChange={(e) => onValj(e.target.value)}
      className={`h-9 rounded-lg border border-input bg-background px-2 text-sm text-deep ${bred ? "w-52" : "w-44"}`}
    >
      {val.map((o) => (
        <option key={o.v} value={o.v}>
          {o.t}
        </option>
      ))}
    </select>
  );
}

/** Medarbetare: uppgifter och villkor som styr schemaoptimeringen. */
export function Medarbetare({ api }: VyProps) {
  const rader = api.medarbetare();
  const [nytt, setNytt] = useState("");
  const [oppen, setOppen] = useState<string | null>(null);

  if (!rader.length) {
    return (
      <TomtLage
        ikon={Upload}
        rubrik="Medarbetarna kommer från schemat"
        text="Läs in det befintliga schemat först – då fylls listan med medarbetare, sysselsättningsgrad och vikarier för de obemannade raderna."
        atgarder={[{ text: "Läs in schema", onClick: () => api.setTab("uppladdning"), ikon: Upload }]}
      />
    );
  }

  const kryss = (namn: string, falt: string, varde: boolean) => (
    <Checkbox checked={varde} onCheckedChange={(v) => api.medarbetareSet(namn, falt, !!v)} aria-label={falt} />
  );
  const antalVikarier = rader.filter((m) => m.vikarie).length;

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Medarbetare</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Uppgifter och villkor</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Raderna kommer från det inlästa schemat. De obemannade raderna blir vikarier och räknas med i alla siffror.
          Fäll ut en rad med pilen för att sätta passprofil, helger, arbetstidsfönster, frånvaro och timkostnad – de
          uppgifterna styr hur appen föreslår schemat.
        </p>
        {antalVikarier ? (
          <p className="mt-3 inline-block rounded-lg bg-warning-soft px-3 py-1.5 text-[13px] font-semibold text-warning">
            {antalVikarier} vikarier från obemannade schemarader
          </p>
        ) : null}
      </Card>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                {["", "Namn", "SSG", "Samordnare", "Delegering", "Sovande jour", "Nattbehörig", "Passprofil"].map(
                  (h, i) => (
                    <th
                      key={h || i}
                      className={`px-4 py-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase ${i <= 1 ? "text-left" : "text-center"}`}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rader.map((m) => (
                <Fragment key={m.namn}>
                  <tr className={`border-t border-border ${m.vikarie ? "bg-warning-soft/60" : ""}`}>
                    <td className="border-t border-border px-3 py-3">
                      <button
                        type="button"
                        aria-label="Visa mer"
                        onClick={() => setOppen((o) => (o === m.namn ? null : m.namn))}
                        className="text-muted-foreground"
                      >
                        {oppen === m.namn ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                      </button>
                    </td>
                    <td className="border-t border-border px-4 py-3 text-sm font-bold text-deep">
                      {m.namn}
                      {m.vikarie ? (
                        <span className="ml-2 rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-bold text-warning">
                          vikarie
                        </span>
                      ) : null}
                      <div className="mt-1 text-[12px] font-medium text-muted-foreground">
                        {m.grad} % · {PASSPROFIL.find((p) => p.v === m.passprofil)?.t || m.passprofil}
                        {m.jour ? " · Kan arbeta jour" : ""}
                        {(m.villkor || []).filter((v) => v.aktiv).length
                          ? ` · ${(m.villkor || []).filter((v) => v.aktiv).length} individuella villkor`
                          : ""}
                      </div>
                    </td>
                    <td className="border-t border-border px-3 py-2 text-center">
                      <Input
                        className="mx-auto h-9 w-20 text-center tabular-nums"
                        value={String(m.grad)}
                        inputMode="numeric"
                        onChange={(e) => api.medarbetareSet(m.namn, "grad", Number(e.target.value) || 0)}
                      />
                    </td>
                    <td className="border-t border-border px-3 py-3 text-center">
                      {kryss(m.namn, "samordnare", m.samordnare)}
                    </td>
                    <td className="border-t border-border px-3 py-3 text-center">
                      {kryss(m.namn, "delegering", m.delegering)}
                    </td>
                    <td className="border-t border-border px-3 py-3 text-center">{kryss(m.namn, "jour", m.jour)}</td>
                    <td className="border-t border-border px-3 py-3 text-center">
                      {kryss(m.namn, "nattbehorig", m.nattbehorig)}
                    </td>
                    <td className="border-t border-border px-3 py-3 text-center">
                      <Val
                        varde={m.passprofil}
                        val={PASSPROFIL}
                        onValj={(v) => api.medarbetareSet(m.namn, "passprofil", v)}
                      />
                    </td>
                  </tr>
                  {oppen === m.namn ? (
                    <tr className="border-t border-border bg-muted/50">
                      <td colSpan={8} className="px-6 py-5">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Helgtjänstgöring</span>
                            <Val varde={m.helg} val={HELG} bred onValj={(v) => api.medarbetareSet(m.namn, "helg", v)} />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Frånvaro/ledighet</span>
                            <Val
                              varde={m.franvaro}
                              val={FRANVARO}
                              bred
                              onValj={(v) => api.medarbetareSet(m.namn, "franvaro", v)}
                            />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Anställning</span>
                            <Val
                              varde={m.anstallning}
                              val={ANSTALLNING}
                              bred
                              onValj={(v) => api.medarbetareSet(m.namn, "anstallning", v)}
                            />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Tidigaste start</span>
                            <Input
                              type="time"
                              className="h-9 w-40"
                              value={m.tidigastStart}
                              onChange={(e) => api.medarbetareSet(m.namn, "tidigastStart", e.target.value)}
                            />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Senaste sluttid</span>
                            <Input
                              type="time"
                              className="h-9 w-40"
                              value={m.senastSlut}
                              onChange={(e) => api.medarbetareSet(m.namn, "senastSlut", e.target.value)}
                            />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Max arbetsdagar i följd</span>
                            <Input
                              className="h-9 w-40 tabular-nums"
                              inputMode="numeric"
                              value={String(m.maxDagarIFoljd)}
                              onChange={(e) =>
                                api.medarbetareSet(
                                  m.namn,
                                  "maxDagarIFoljd",
                                  Math.min(7, Math.max(1, Number(e.target.value) || 1)),
                                )
                              }
                            />
                          </label>
                          <label className="space-y-1 text-sm">
                            <span className="block font-semibold text-deep">Timkostnad (kr/h)</span>
                            <Input
                              className="h-9 w-40 tabular-nums"
                              inputMode="numeric"
                              value={String(m.timkostnad)}
                              onChange={(e) => api.medarbetareSet(m.namn, "timkostnad", Number(e.target.value) || 0)}
                            />
                          </label>
                        </div>
                        <div className="mt-5 space-y-2">
                          <span className="block text-sm font-semibold text-deep">Individuella villkor</span>
                          <p className="text-[12px] text-muted-foreground">
                            Datumfönster per person. Hårda villkor styr motorn; önskemål sparas men vägs inte in i
                            CP-SAT i den här versionen.
                          </p>
                          {(m.villkor || []).map((v, ix) => (
                            <div key={v.id || ix} className="flex flex-wrap items-end gap-2 rounded-lg bg-background p-2">
                              <select
                                className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
                                value={v.typ}
                                onChange={(e) => {
                                  const nasta = (m.villkor || []).map((x, i) =>
                                    i === ix ? { ...x, typ: e.target.value } : x,
                                  );
                                  api.medarbetareSet(m.namn, "villkor", nasta);
                                }}
                              >
                                <option value="ssg">SSG</option>
                                <option value="ingen_natt">Ingen natt</option>
                                <option value="endast_dag">Endast dag</option>
                                <option value="ingen_jour">Ingen jour</option>
                                <option value="kundforbud">Kundförbud</option>
                              </select>
                              <select
                                className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
                                value={v.styrka}
                                onChange={(e) => {
                                  const nasta = (m.villkor || []).map((x, i) =>
                                    i === ix ? { ...x, styrka: e.target.value } : x,
                                  );
                                  api.medarbetareSet(m.namn, "villkor", nasta);
                                }}
                              >
                                <option value="maste">Måste</option>
                                <option value="onskemal">Önskemål</option>
                              </select>
                              <Input
                                type="date"
                                className="h-9 w-36"
                                value={v.from || ""}
                                onChange={(e) => {
                                  const nasta = (m.villkor || []).map((x, i) =>
                                    i === ix ? { ...x, from: e.target.value } : x,
                                  );
                                  api.medarbetareSet(m.namn, "villkor", nasta);
                                }}
                              />
                              <Input
                                type="date"
                                className="h-9 w-36"
                                value={v.till || ""}
                                onChange={(e) => {
                                  const nasta = (m.villkor || []).map((x, i) =>
                                    i === ix ? { ...x, till: e.target.value } : x,
                                  );
                                  api.medarbetareSet(m.namn, "villkor", nasta);
                                }}
                              />
                              {v.typ === "ssg" ? (
                                <Input
                                  className="h-9 w-20 tabular-nums"
                                  inputMode="numeric"
                                  value={String(v.payload?.["ssg"] ?? "")}
                                  onChange={(e) => {
                                    const nasta = (m.villkor || []).map((x, i) =>
                                      i === ix ? { ...x, payload: { ...x.payload, ssg: Number(e.target.value) || 0 } } : x,
                                    );
                                    api.medarbetareSet(m.namn, "villkor", nasta);
                                  }}
                                />
                              ) : null}
                              {v.typ === "kundforbud" ? (
                                <Input
                                  className="h-9 w-40"
                                  placeholder="Kundnamn"
                                  value={String(v.payload?.["kund"] ?? "")}
                                  onChange={(e) => {
                                    const nasta = (m.villkor || []).map((x, i) =>
                                      i === ix ? { ...x, payload: { ...x.payload, kund: e.target.value } } : x,
                                    );
                                    api.medarbetareSet(m.namn, "villkor", nasta);
                                  }}
                                />
                              ) : null}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  api.medarbetareSet(
                                    m.namn,
                                    "villkor",
                                    (m.villkor || []).filter((_, i) => i !== ix),
                                  )
                                }
                              >
                                Ta bort
                              </Button>
                            </div>
                          ))}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              api.medarbetareSet(m.namn, "villkor", [
                                ...(m.villkor || []),
                                {
                                  id: `v${Date.now()}`,
                                  typ: "ssg",
                                  styrka: "maste",
                                  aktiv: true,
                                  from: "",
                                  till: "",
                                  payload: { ssg: m.grad },
                                },
                              ])
                            }
                          >
                            Lägg till villkor
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-4">
          <Input
            className="h-10 w-56"
            placeholder="Namn på ny medarbetare"
            value={nytt}
            onChange={(e) => setNytt(e.target.value)}
          />
          <Button
            variant="outline"
            onClick={() => {
              api.medarbetareLaggTill(nytt);
              setNytt("");
            }}
          >
            <Plus /> Lägg till medarbetare
          </Button>
        </div>
      </Card>

      <Card className="gap-0 rounded-2xl border-primary/30 bg-primary-soft/60 p-6 shadow-lift">
        <div className="flex gap-3">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <p className="text-sm leading-relaxed text-deep">
            Ändrar du något här nollställs resultatet – skapa bemanningsbalansen igen så räknas allt om. Jouren börjar
            kl. 23.00 och slutar kl. 06.30, även på helger.
          </p>
        </div>
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-4 rounded-2xl p-7 shadow-lift">
        <span className="text-sm text-muted-foreground">
          Appen optimerar kundinsatser och schema utifrån era behov och villkor.
        </span>
        <Button onClick={() => api.skapaBalans()}>
          Skapa bemanningsbalans <ArrowRight />
        </Button>
      </Card>
    </div>
  );
}
