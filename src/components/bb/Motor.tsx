import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, CircleAlert, Cpu, Loader2, RotateCcw, ShieldCheck, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { VyProps } from "@/lib/bb/vy";
import { byggMotorPayload, type PayloadResultat } from "@/lib/bb/motorPayload";
import { delaPeriod, payloadForFonster, svansPass, type Fonster } from "@/lib/bb/motorPeriod";
import { REGEL_RUBRIK, betaldTid, passForandringar, slaSamman, tolkaMotorSchema, type MotorSchema } from "@/lib/bb/motorResultat";
import { motorStatus, optimeraMedMotor, type MotorSvar } from "@/lib/bb/motor.functions";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

type Korning = {
  fonster: Fonster;
  status: string;
  forklaring: string;
  sekunder?: number | undefined;
  fel: { rule?: string; message?: string }[];
  meddelande?: string | undefined;
};

export function Motor({ state, api }: VyProps) {
  const [jobbar, setJobbar] = useState(false);
  const [steg, setSteg] = useState("");
  const [klar, setKlar] = useState(api.harBalans());
  const [motorKlar, setMotorKlar] = useState<boolean | null>(null);
  const [motorMeddelande, setMotorMeddelande] = useState("");
  const [korningar, setKorningar] = useState<Korning[]>([]);
  const [kalla, setKalla] = useState<"motor" | "lokal" | null>(api.berakningsKalla());
  const [sekunder, setSekunder] = useState(45);
  const [diagnos, setDiagnos] = useState<string[]>([]);
  const [avvisat, setAvvisat] = useState<string>("");
  const [underlagsVarningar, setUnderlagsVarningar] = useState<string[]>([]);
  const [obemannade, setObemannade] = useState<{ insats: string; datum: string; minuter: number; antal: number }[]>([]);
  const senastePayload = useRef<PayloadResultat | null>(null);

  const underlag = api.underlag();
  const harData = api.harUnderlag();

  useEffect(() => {
    let levande = true;
    motorStatus()
      .then((s) => {
        if (levande) {
          setMotorKlar(Boolean(s?.installd && s?.klar));
          setMotorMeddelande(String(s?.meddelande || ""));
        }
      })
      .catch(() => {
        if (levande) setMotorKlar(false);
      });
    return () => {
      levande = false;
    };
  }, []);

  const bygg = () => {
    const period = (state?.period ?? null) as { from?: string } | null;
    const rader = api.arbetsRader();
    const personal = api.harPersonal() ? api.personalRader() : [];
    const heltid = Number(personal[0]?.["Heltid h/vecka"]) || 36.33;
    return byggMotorPayload({
      rader,
      medarbetare: api.medarbetare(),
      from: String(period?.from || rader[0]?.datum || "").slice(0, 10),
      dagar: api.planDays(),
      timkostnad: Number(state?.hourlyCost) || 270,
      heltidVecka: heltid,
      regler: api.motorRegler(),
      schemaPass: api.schemaPassOriginal(),
      objectiveWeights: {
        continuitySek: Number(state?.["continuitySek"] ?? 50),
        spreadSekPerPermille: Number(state?.["spreadSekPerPermille"] ?? 2.5),
      },
    });
  };

  /** Vanliga orsaker till att inga hårda villkor kan uppfyllas – räknat på underlaget. */
  const byggDiagnos = (p: PayloadResultat) => {
    const ut: string[] = [];
    const anstallda = (p.payload["employees"] as { status: string; skills: string[]; night: boolean; ssg: number }[]) || [];
    const aktiva = anstallda.filter((e) => e.status === "active");
    const insatser = (p.payload["interventions"] as { skills: string[]; minutes: number }[]) || [];
    const utanKompetens = insatser.filter((i) => i.skills.length && !aktiva.some((e) => i.skills.every((s) => e.skills.includes(s))));
    if (utanKompetens.length) ut.push(`${utanKompetens.length} insatser kräver en kompetens som ingen tillgänglig medarbetare har.`);
    const nattgolv = p.info.regler.nightFloor;
    const nattpersonal = aktiva.filter((e) => e.night).length;
    if (nattgolv > nattpersonal) ut.push(`Vaken natt kräver ${nattgolv} medarbetare men bara ${nattpersonal} har nattbehörighet.`);
    const heltid = Number((p.payload["rules"] as { fullTimeWeeklyHours: number }).fullTimeWeeklyHours) || 36.33;
    const tak = aktiva.reduce((s, e) => s + (e.ssg / 100) * heltid * (p.info.dagar / 7), 0);
    const behov = insatser.reduce((s, i) => s + i.minutes, 0) / 60;
    if (tak < behov) ut.push(`Personalens sysselsättningsgrader ger högst ${tak.toFixed(0)} timmar i perioden, men insatserna kräver minst ${behov.toFixed(0)} timmar.`);
    if (!ut.length) ut.push("Underlaget ser rimligt ut på ytan – titta på tidsfönster, frånvaro och passmallar.");
    return ut;
  };

  const lokalBerakning = () => {
    api.skapa();
    setKlar(api.harBalans());
    setKalla("lokal");
  };

  const kor = async (tid = 45) => {
    setJobbar(true);
    setKlar(false);
    setKorningar([]);
    setDiagnos([]);
    setAvvisat("");
    setSekunder(tid);
    setKalla(null);
    setObemannade([]);

    let tillganglig = motorKlar;
    if (tillganglig === null) {
      setSteg("Kontrollerar anslutningen till optimeringsmotorn…");
      try {
        const status = await motorStatus();
        tillganglig = Boolean(status?.installd && status?.klar);
        setMotorKlar(tillganglig);
        setMotorMeddelande(String(status?.meddelande || ""));
      } catch (e) {
        tillganglig = false;
        setMotorKlar(false);
        setMotorMeddelande((e as Error).message);
      }
    }
    if (!tillganglig) {
      setSteg("Optimeringsmotorn är inte nåbar – räknar i appen.");
      setTimeout(() => {
        try {
          lokalBerakning();
        } finally {
          setJobbar(false);
          setSteg("");
        }
      }, 60);
      return;
    }

    const underlagMotor = bygg();
    senastePayload.current = underlagMotor;
    setUnderlagsVarningar(underlagMotor.varningar);
    const insatser = (underlagMotor.payload["interventions"] as { date?: string }[]) || [];
    const fonster = delaPeriod(underlagMotor.info.from, underlagMotor.info.to, insatser);
    const delar: MotorSchema[] = [];
    const loggar: Korning[] = [];
    let lasta: Record<string, unknown>[] = [];

    try {
      for (let i = 0; i < fonster.length; i++) {
        const f = fonster[i]!;
        setSteg(`Fönster ${i + 1} av ${fonster.length}: ${f.from} – ${f.to} (${f.insatser} insatser)`);
        const del = payloadForFonster(underlagMotor.payload, f, lasta);
        let svar: MotorSvar | null = null;
        for (let forsok = 0; forsok < 6; forsok++) {
          svar = await optimeraMedMotor({ data: { data: del, seconds: tid } });
          if (svar.ok || svar.status !== "429") break;
          setSteg(`En beräkning pågår redan – försöker igen (${forsok + 1}/6)…`);
          await new Promise((r) => setTimeout(r, 5000));
        }
        if (!svar || !svar.ok) {
          if (svar?.status === "422") setAvvisat(svar.meddelande || "");
          loggar.push({ fonster: f, status: svar?.status ?? "FEL", forklaring: "", fel: svar?.fel ?? [], meddelande: svar?.meddelande });
          setKorningar([...loggar]);
          setDiagnos(byggDiagnos(underlagMotor));
          // Ingen ska bli stående utan förslag: appen räknar fram ett i stället.
          lokalBerakning();
          setJobbar(false);
          setSteg("");
          return;
        }
        const schema = svar.schemaJson
          ? tolkaMotorSchema(svar.schemaJson, { medarbetare: underlagMotor.medarbetarKarta, insatser: underlagMotor.insatsKarta })
          : null;
        loggar.push({
          fonster: f,
          status: svar.status ?? "UNKNOWN",
          forklaring: svar.forklaring ?? "",
          sekunder: svar.sekunder,
          fel: svar.fel ?? [],
        });
        setKorningar([...loggar]);
        if (!schema || !schema.pass.length || svar.status === "INFEASIBLE" || svar.status === "UNKNOWN" || svar.status === "MODEL_INVALID") {
          setDiagnos(byggDiagnos(underlagMotor));
          lokalBerakning();
          setJobbar(false);
          setSteg("");
          return;
        }
        delar.push(schema);
        const rapass = (JSON.parse(svar.schemaJson || "{}").shifts as Record<string, unknown>[]) || [];
        lasta = svansPass(rapass).map((p) => ({ ...p, last: true }));
      }

      const samlat = slaSamman(delar);
      if (!samlat) {
        setDiagnos(byggDiagnos(underlagMotor));
        return;
      }
      const original = api.schemaPassOriginal();
      const forandringar = passForandringar(original, samlat.pass);
      setObemannade(samlat.obemannade);
      const obemannadeTimmar = samlat.obemannade.reduce((s, u) => s + (u.minuter * u.antal) / 60, 0);
      const extraVarningar = obemannadeTimmar
        ? [
            `${samlat.obemannade.length} insatstillfällen (${obemannadeTimmar.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} timmar) kunde inte bemannas utan att bryta mot vila-, helg- eller jourreglerna. De listas nedan.`,
          ]
        : [];
      const infordes = api.anvandMotorResultat({
        pass: samlat.pass,
        flyttade: samlat.flyttade,
        forandringar,
        varningar: [...underlagMotor.varningar, ...extraVarningar],
        solverStatus: samlat.solverStatus,
        explanation: samlat.explanation,
        tilldelningar: samlat.tilldelningar,
        fonster: fonster.length,
        objectiveBreakdown: samlat.objectiveBreakdown,
      });
      if (infordes) {
        setKlar(true);
        setKalla("motor");
      }
    } catch (e) {
      loggar.push({ fonster: fonster[0]!, status: "FEL", forklaring: "", fel: [], meddelande: (e as Error).message });
      setKorningar([...loggar]);
      lokalBerakning();
    } finally {
      setJobbar(false);
      setSteg("");
    }
  };

  const aterstall = () => {
    api.aterstallBalans();
    setKlar(false);
    setKorningar([]);
    setKalla(null);
    setDiagnos([]);
    setObemannade([]);
  };

  const forandringar = klar ? api.schemaForandringar() : [];
  const varningar = klar ? api.schemaVarningar() : [];
  const pass = klar ? api.schemaPass() : [];
  const fe = klar ? api.foreEfter() : null;
  const vikarier = klar ? api.vikarieBeslut() : [];
  const brott = klar ? api.regelbrott() : 0;
  const flyttade = fe?.flyttade ?? [];
  const senaste = korningar[korningar.length - 1] ?? null;
  const motorTimmar = pass.reduce((s, p) => s + betaldTid(p.start, p.slut), 0);

  const statusFarg = (s: string) =>
    s === "OPTIMAL" ? "var(--ok)" : s === "FEASIBLE" ? "var(--varn)" : "var(--fara)";
  const statusText = (s: string) =>
    s === "OPTIMAL"
      ? "Bevisat optimal"
      : s === "FEASIBLE"
        ? "Giltig lösning (ej bevisat bästa)"
        : s === "INFEASIBLE"
          ? "Inga hårda villkor kan uppfyllas samtidigt"
          : s === "UNKNOWN"
            ? "Tiden räckte inte"
            : s === "MODEL_INVALID"
              ? "Förslaget stoppades av kontrollen"
              : s === "422"
                ? "Underlaget avvisades"
                : s === "503"
                  ? "Motorn saknar sin beräkningsdel"
                  : "Motorn är inte nåbar";

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <Eyebrow>Optimeringsmotor</Eyebrow>
            <h2 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-deep">
              <Cpu className="size-6 text-primary" /> Skapa bemanningsbalans
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Bemanningsbalansen räknas fram utifrån kundernas behov och verksamhetens regler. Ditt befintliga schema
              ändras aldrig – du får ett förslag att titta på.
            </p>
            <p className="mt-2 text-xs font-semibold text-muted-foreground">
              {motorKlar === null
                ? "Kontrollerar vilken beräkning som är tillgänglig…"
                : motorKlar
                  ? "Den bevisat optimerande beräkningen är tillgänglig och används."
                   : `Den bevisat optimerande beräkningen är inte tillgänglig – appen räknar själv (reservläge).${motorMeddelande ? ` ${motorMeddelande}` : ""}`}
            </p>
          </div>
          {klar ? (
            <Button variant="outline" onClick={aterstall} disabled={jobbar}>
              <RotateCcw /> Börja om
            </Button>
          ) : null}
        </div>
      </Card>

      <Card className="gap-0 rounded-2xl p-7 shadow-lift">
        <Eyebrow>Underlag</Eyebrow>
        {harData ? (
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            {underlag?.period ? (
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {underlag.period.from} – {underlag.period.to}
              </Badge>
            ) : null}
            {underlag?.sekoia ? (
              <>
                <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                  {underlag.sekoia.insatser} insatser
                </Badge>
                <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                  {underlag.sekoia.kunder} kunder
                </Badge>
              </>
            ) : null}
            {underlag?.schema ? (
              <>
                <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                  {underlag.schema.medarbetare} medarbetare
                </Badge>
                <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                  {underlag.schema.pass} pass
                </Badge>
              </>
            ) : null}
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            Läs in kundernas behov och personalschemat under Ladda upp underlag först.
          </p>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          <Button onClick={() => kor(45)} disabled={!harData || jobbar}>
            {jobbar ? <Loader2 className="animate-spin" /> : <Cpu />}
            {jobbar ? "Räknar…" : klar ? "Skapa om bemanningsbalans" : "Skapa bemanningsbalans"}
          </Button>
          {!jobbar && senaste && (senaste.status === "FEASIBLE" || senaste.status === "UNKNOWN") ? (
            <Button variant="outline" onClick={() => kor(55)}>
              Försök igen
            </Button>
          ) : null}
          {!jobbar && senaste && !klar ? (
            <Button variant="outline" onClick={lokalBerakning}>
              Räkna i appen i stället (reservläge)
            </Button>
          ) : null}
        </div>
        {jobbar && steg ? <p className="mt-3 text-xs font-semibold text-muted-foreground">{steg}</p> : null}
        {underlagsVarningar.length ? (
          <ul className="mt-4 space-y-1.5 text-sm text-warning">
            {underlagsVarningar.map((v, i) => (
              <li key={i} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {v}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      {korningar.length ? (
        <Card className="gap-0 rounded-2xl p-7 shadow-lift" style={{ borderLeftWidth: 4, borderLeftColor: statusFarg(senaste?.status ?? "") }}>
          <Eyebrow>Så räknades förslaget</Eyebrow>
          <h4 className="mt-1 text-sm font-bold text-deep">
            {statusText(senaste?.status ?? "")}
            {korningar.length > 1 ? ` – beräknat i ${korningar.length} delperioder` : ""}
          </h4>
          <ul className="mt-3 space-y-1.5 text-sm text-deep">
            {korningar.map((k, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
                  {k.fonster.from} – {k.fonster.to}
                </Badge>
                <span className="text-xs font-semibold">{statusText(k.status)}</span>
                {typeof k.sekunder === "number" ? (
                  <span className="text-xs text-muted-foreground">{k.sekunder.toFixed(1)} sekunders räknetid</span>
                ) : null}
              </li>
            ))}
          </ul>
          {senaste?.forklaring ? <p className="mt-3 text-sm text-muted-foreground">{senaste.forklaring}</p> : null}
          {avvisat ? <p className="mt-3 text-sm text-danger">Underlaget avvisades: {avvisat}</p> : null}
          {senaste?.meddelande && !avvisat ? <p className="mt-3 text-sm text-warning">{senaste.meddelande}</p> : null}
          {senaste?.fel?.length ? (
            <ul className="mt-3 space-y-1 text-sm text-danger">
              {senaste.fel.slice(0, 20).map((f, i) => (
                <li key={i} className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  <span>
                    <span className="font-semibold">{REGEL_RUBRIK[String(f.rule)] ?? f.rule}: </span>
                    {f.message}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          {diagnos.length ? (
            <div className="mt-4 rounded-xl bg-muted/60 p-4">
              <h5 className="text-sm font-bold text-deep">Vad som troligen står i vägen</h5>
              <ul className="mt-2 space-y-1 text-sm text-deep">
                {diagnos.map((t, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" /> {t}
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => api.setTab("bemanning")}>
                  Öppna Medarbetare
                </Button>
                <Button variant="outline" size="sm" onClick={() => api.setTab("villkor")}>
                  Öppna Styrande villkor
                </Button>
              </div>
            </div>
          ) : null}
          <p className="mt-3 text-xs text-muted-foreground">
            Förslaget visas som underlag – ert schema ändras först när du själv väljer att införa det.
            {sekunder !== 180 ? ` Räknetid: ${sekunder} sekunder.` : ""}
          </p>
        </Card>
      ) : null}

      {klar && kalla === "lokal" ? (
        <Card className="gap-0 rounded-2xl p-5 shadow-lift" style={{ borderLeftWidth: 4, borderLeftColor: "var(--varn)" }}>
          <p className="text-sm font-semibold text-deep">
            Reservläge: förslaget är beräknat i appen, utan den bevisat optimerande beräkningen.
          </p>
        </Card>
      ) : null}

      {klar && fe?.efter ? (
        <>
          <Card
            className="gap-0 rounded-2xl p-7 shadow-lift"
            style={{ borderLeftWidth: 4, borderLeftColor: brott ? "var(--fara)" : "var(--ok)" }}
          >
            <Eyebrow>Resultat</Eyebrow>
            <h3 className="mt-1 flex items-center gap-2 text-lg font-extrabold text-deep">
              {brott ? (
                <><CircleAlert className="size-5 text-danger" /> Förslag med {brott} varningar</>
              ) : (
                <><Check className="size-5 text-success" /> Förslag klart – inga regelbrott</>
              )}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Förslaget ersätter aldrig ert schema automatiskt – det gäller först när du själv väljer att införa det.
            </p>

            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {pass.length} pass i förslaget
              </Badge>
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {motorTimmar.toLocaleString("sv-SE", { maximumFractionDigits: 1 })} schematimmar
              </Badge>
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {flyttade.length} insatser flyttade
              </Badge>
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {forandringar.length} pass ändrade
              </Badge>
              <Badge variant="secondary" className="rounded-full px-3 py-1 font-bold">
                {obemannade.reduce((s, u) => s + u.antal, 0)} obemannade insatser
              </Badge>
            </div>

            {obemannade.length ? (
              <div className="mt-6 rounded-xl bg-muted/60 p-4">
                <h4 className="text-sm font-bold text-deep">Behov som inte kunde bemannas</h4>
                <p className="mt-1 text-xs text-muted-foreground">
                  Alla övriga insatser är bemannade. Dessa gick inte att lägga utan att bryta mot vila-, helg- eller
                  jourreglerna.
                </p>
                <ul className="mt-3 space-y-1 text-sm text-deep">
                  {obemannade.slice(0, 30).map((u, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
                      <span>
                        {u.datum} · {u.insats} · {u.minuter} minuter
                        {u.antal > 1 ? ` · ${u.antal} tillfällen` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
                {obemannade.length > 30 ? (
                  <p className="mt-2 text-xs text-muted-foreground">…och {obemannade.length - 30} till.</p>
                ) : null}
              </div>
            ) : null}

            {fe.tabell.length ? (
              <div className="mt-6 overflow-x-auto">
                <h4 className="mb-2 text-sm font-bold text-deep">Före och efter</h4>
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-4 font-semibold">Mått</th>
                      <th className="py-2 pr-4 font-semibold">Före</th>
                      <th className="py-2 pr-4 font-semibold">Efter</th>
                      <th className="py-2 font-semibold">Ändring</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fe.tabell.map((rad, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="py-2 pr-4 font-medium text-deep">{rad.namn}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{rad.fore}</td>
                        <td className="py-2 pr-4 font-semibold text-deep">{rad.efter}</td>
                        <td
                          className={
                            "py-2 font-bold " +
                            (rad.riktning === "upp"
                              ? "text-success"
                              : rad.riktning === "ner"
                                ? "text-danger"
                                : "text-muted-foreground")
                          }
                        >
                          {rad.forandring}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Card>

          {forandringar.length ? (
            <Card className="gap-0 rounded-2xl p-7 shadow-lift">
              <Eyebrow>Passändringar</Eyebrow>
              <h4 className="mt-1 text-sm font-bold text-deep">Så här har passen justerats</h4>
              <ul className="mt-3 space-y-1.5 text-sm text-deep">
                {forandringar.slice(0, 50).map((f, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <ArrowRight className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>
                      <span className="font-semibold capitalize">{f.typ}:</span> {f.text}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {varningar.length ? (
            <Card className="gap-0 rounded-2xl p-7 shadow-lift">
              <Eyebrow>Regelvarningar</Eyebrow>
              <h4 className="mt-1 flex items-center gap-2 text-sm font-bold text-deep">
                <ShieldCheck className="size-4 text-warning" /> Att titta närmare på
              </h4>
              <ul className="mt-3 space-y-1.5 text-sm text-warning">
                {varningar.slice(0, 40).map((v, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {v.text}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {vikarier.length ? (
            <Card className="gap-0 rounded-2xl p-7 shadow-lift">
              <Eyebrow>Vikariepass</Eyebrow>
              <h4 className="mt-1 text-sm font-bold text-deep">Vikariebeslut</h4>
              <ul className="mt-3 space-y-1.5 text-sm text-deep">
                {vikarier.slice(0, 40).map((v, i) => (
                  <li key={i} className="flex items-start gap-2">
                    {v.behovs ? (
                      <Check className="mt-0.5 size-4 shrink-0 text-success" />
                    ) : (
                      <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    )}
                    <span>
                      {v.namn} {v.datum} {v.start}–{v.slut}:{" "}
                      {v.behovs
                        ? "behöver tillsättas – fyller ett verkligt gap"
                        : "kan tas bort – behovet täcks av ordinarie personal"}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </>
      ) : null}

      {jobbar && !klar ? (
        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <div className="flex items-center gap-3 text-sm font-semibold text-deep">
            <Loader2 className="size-5 animate-spin text-primary" />
            Räknar… {steg}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
