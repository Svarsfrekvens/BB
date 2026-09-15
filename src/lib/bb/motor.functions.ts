/* ------------------------------------------------------------------ *
 * Skyddad koppling till optimeringsmotorn. Adress och hemlig nyckel
 * läses på servern – de syns aldrig i webbläsaren.
 * ------------------------------------------------------------------ */

import { createServerFn } from "@tanstack/react-start";

export type MotorSvar = {
  ok: boolean;
  status?: string;
  forklaring?: string;
  sekunder?: number;
  pass?: number;
  tilldelningar?: number;
  giltigt?: boolean | null;
  fel?: { rule?: string; message?: string }[];
  varningar?: { rule?: string; message?: string }[];
  schemaJson?: string | null;
  summary?: Record<string, unknown> | null;
  resourceDiagnostics?: Record<string, unknown> | null;
  meddelande?: string;
};

export type MotorJobbSvar = {
  ok: boolean;
  jobId?: string;
  status?: string;
  phase?: string;
  phaseText?: string;
  stillSearching?: boolean;
  inputHash?: string;
  inputRevision?: unknown;
  reused?: boolean;
  outcome?: string | null;
  error?: string | null;
  progress?: {
    incumbents?: number;
    elapsedS?: number | null;
    uncoveredMinutes?: number | null;
    bound?: number | null;
  };
  result?: MotorSvar;
  meddelande?: string;
};

function bas() {
  const url = process.env["OPTIMIZER_URL"];
  const token = process.env["OPTIMIZER_TOKEN"];
  return { url: url ? url.replace(/\/+$/, "") : "", token: token || "" };
}

function motorFranOptimizeJson(data: any): MotorSvar {
  const schema = data?.schedule ?? null;
  const validering = data?.validation ?? null;
  return {
    ok: true,
    status: schema?.solverStatus ?? (validering ? (validering.valid ? "OK" : "MODEL_INVALID") : "UNKNOWN"),
    forklaring: schema?.explanation,
    sekunder: schema?.seconds,
    pass: Array.isArray(schema?.shifts) ? schema.shifts.length : undefined,
    tilldelningar: Array.isArray(schema?.assignments) ? schema.assignments.length : undefined,
    giltigt: validering ? Boolean(validering.valid) : null,
    fel: validering?.errors ?? [],
    varningar: validering?.warnings ?? [],
    schemaJson: schema ? JSON.stringify(schema) : null,
    summary: data?.summary && typeof data.summary === "object" ? data.summary : null,
    resourceDiagnostics:
      data?.resourceDiagnostics && typeof data.resourceDiagnostics === "object"
        ? data.resourceDiagnostics
        : schema?.resourceDiagnostics && typeof schema.resourceDiagnostics === "object"
          ? schema.resourceDiagnostics
          : null,
  };
}

function jobbFranJson(data: any, httpOk: boolean, fallback: string): MotorJobbSvar {
  if (!httpOk) {
    return { ok: false, status: data?.status, meddelande: fallback };
  }
  const result = data?.result ? motorFranOptimizeJson(data.result) : undefined;
  const view: MotorJobbSvar = {
    ok: true,
    jobId: data?.jobId,
    status: data?.status,
    phase: data?.phase,
    phaseText: data?.phaseText,
    stillSearching: Boolean(data?.stillSearching),
    inputHash: data?.inputHash,
    inputRevision: data?.inputRevision,
    reused: Boolean(data?.reused),
    outcome: data?.outcome ?? null,
    error: data?.error ?? null,
  };
  if (data?.progress && typeof data.progress === "object") view.progress = data.progress;
  if (result) view.result = result;
  return view;
}

async function anropa(vag: string, kropp: unknown): Promise<MotorSvar> {
  const { url, token } = bas();
  if (!url) {
    return { ok: false, meddelande: "Optimeringsmotorns adress är inte inställd ännu." };
  }
  let svar: Response;
  try {
    svar = await fetch(`${url}${vag}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(kropp),
    });
  } catch (e) {
    return { ok: false, meddelande: `Motorn svarar inte: ${(e as Error).message}` };
  }
  const text = await svar.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!svar.ok) {
    const detalj = typeof data?.detail === "string" ? data.detail : text.slice(0, 300);
    return { ok: false, status: String(svar.status), meddelande: detalj || "Optimeringen misslyckades." };
  }
  return motorFranOptimizeJson(data);
}

async function anropaJobb(method: "GET" | "POST", vag: string, kropp?: unknown): Promise<MotorJobbSvar> {
  const { url, token } = bas();
  if (!url) {
    return { ok: false, meddelande: "Optimeringsmotorns adress är inte inställd ännu." };
  }
  let svar: Response;
  try {
    svar = await fetch(`${url}${vag}`, {
      method,
      headers: {
        ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(method === "POST" ? { body: JSON.stringify(kropp) } : {}),
    });
  } catch (e) {
    return { ok: false, meddelande: `Motorn svarar inte: ${(e as Error).message}` };
  }
  const text = await svar.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  const detalj = typeof data?.detail === "string" ? data.detail : text.slice(0, 300);
  return jobbFranJson(data, svar.ok, detalj || "Beräkningen kunde inte läsas.");
}

/** Räknar fram ett schemaförslag. Det befintliga schemat ändras inte. */
export const optimeraMedMotor = createServerFn({ method: "POST" })
  .inputValidator((input: { data: unknown; seconds?: number }) => input)
  .handler(async ({ data }) =>
    anropa("/api/optimize", { data: data.data, seconds: Math.min(300, Math.max(5, data.seconds ?? 60)) }),
  );

export const startaMotorJobb = createServerFn({ method: "POST" })
  .inputValidator((input: { data: unknown; seconds?: number }) => input)
  .handler(async ({ data }) =>
    anropaJobb("POST", "/api/optimize/jobs", {
      data: data.data,
      seconds: Math.min(300, Math.max(5, data.seconds ?? 180)),
    }),
  );

export const hamtaMotorJobb = createServerFn({ method: "POST" })
  .inputValidator((input: { jobId: string }) => input)
  .handler(async ({ data }) => anropaJobb("GET", `/api/optimize/jobs/${encodeURIComponent(data.jobId)}`));

/** Granskar ett schema mot motorns regler. */
export const granskaMedMotor = createServerFn({ method: "POST" })
  .inputValidator((input: { data: unknown; schedule?: unknown }) => input)
  .handler(async ({ data }) =>
    anropa("/api/validate", data.schedule ? { data: data.data, schedule: data.schedule } : { data: data.data }),
  );

/** Kontrollerar att motorn är nåbar och klar att räkna. */
export const motorStatus = createServerFn({ method: "GET" }).handler(async () => {
  const { url, token } = bas();
  if (!url) return { installd: false, klar: false, asyncJobs: false, meddelande: "Adress saknas." };
  try {
    const svar = await fetch(`${url}/api/health`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const data: any = await svar.json().catch(() => null);
    return {
      installd: true,
      klar: Boolean(data?.ready),
      asyncJobs: Boolean(data?.limits?.asyncJobs),
      meddelande: svar.ok ? "" : `Svar ${svar.status}`,
    };
  } catch (e) {
    return { installd: true, klar: false, asyncJobs: false, meddelande: (e as Error).message };
  }
});
