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
  meddelande?: string;
};

/** Publik Render-adress. Token är hemlig och läses bara på servern. */
const STANDARD_MOTOR_URL = "https://bemanningsbalans-motor.onrender.com";

function lasEnv(namn: string) {
  const vite = (import.meta as { env?: Record<string, string | undefined> }).env;
  const v = process.env[namn] || process.env[`VITE_${namn}`] || vite?.[namn] || vite?.[`VITE_${namn}`] || "";
  return String(v).trim();
}

function bas() {
  const url = (lasEnv("OPTIMIZER_URL") || STANDARD_MOTOR_URL).replace(/\/+$/, "");
  const token = lasEnv("OPTIMIZER_TOKEN");
  return { url, token };
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
    console.error("[MOTOR] HTTP error", svar.status, detalj);
    return { ok: false, status: String(svar.status), meddelande: detalj || "Optimeringen misslyckades." };
  }
  const schema = data?.schedule ?? null;
  const validering = data?.validation ?? null;
  const status = schema?.solverStatus ?? (validering ? (validering.valid ? "OK" : "MODEL_INVALID") : "UNKNOWN");
  console.error("[MOTOR] response", { status, shifts: Array.isArray(schema?.shifts) ? schema.shifts.length : 0, assignments: Array.isArray(schema?.assignments) ? schema.assignments.length : 0, seconds: schema?.seconds, valid: validering ? validering.valid : null });
  return {
    ok: true,
    status,
    forklaring: schema?.explanation,
    sekunder: schema?.seconds,
    pass: Array.isArray(schema?.shifts) ? schema.shifts.length : undefined,
    tilldelningar: Array.isArray(schema?.assignments) ? schema.assignments.length : undefined,
    giltigt: validering ? Boolean(validering.valid) : null,
    fel: validering?.errors ?? [],
    varningar: validering?.warnings ?? [],
    schemaJson: schema ? JSON.stringify(schema) : null,
  };
}

/** Räknar fram ett schemaförslag. Det befintliga schemat ändras inte. */
export const optimeraMedMotor = createServerFn({ method: "POST" })
  .inputValidator((input: { data: unknown; seconds?: number }) => input)
  .handler(async ({ data }) =>
    anropa("/api/optimize", { data: data.data, seconds: Math.min(300, Math.max(5, data.seconds ?? 60)) }),
  );

/** Granskar ett schema mot motorns regler. */
export const granskaMedMotor = createServerFn({ method: "POST" })
  .inputValidator((input: { data: unknown; schedule?: unknown }) => input)
  .handler(async ({ data }) =>
    anropa("/api/validate", data.schedule ? { data: data.data, schedule: data.schedule } : { data: data.data }),
  );

/** Kontrollerar att motorn är nåbar och klar att räkna. */
export const motorStatus = createServerFn({ method: "GET" }).handler(async () => {
  const { url, token } = bas();
  if (!url) return { installd: false, klar: false, meddelande: "Adress saknas." };
  try {
    const svar = await fetch(`${url}/api/health`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const data: any = await svar.json().catch(() => null);
    if (!svar.ok) {
      const varfor =
        svar.status === 401
          ? "Token saknas eller stämmer inte (OPTIMIZER_TOKEN / BB_API_TOKEN)."
          : `Svar ${svar.status}`;
      return { installd: true, klar: false, meddelande: varfor };
    }
    if (!token) {
      return {
        installd: true,
        klar: false,
        meddelande: "OPTIMIZER_TOKEN saknas i servern. Hälsokollen kan svara ändå – beräkning kräver token.",
      };
    }
    return { installd: true, klar: Boolean(data?.ready), meddelande: data?.ready ? "" : "Motorn svarar men OR-Tools saknas." };
  } catch (e) {
    return { installd: true, klar: false, meddelande: (e as Error).message };
  }
});
