/* ------------------------------------------------------------------ *
 * Liten notisbuss. Logiklagret säger vad som hände; React-lagret
 * bestämmer hur det ser ut (sonner-toast). Ingen beräkning här.
 * ------------------------------------------------------------------ */

export type NotisTon = "ok" | "fel" | "info";

export type Notis = {
  id: number;
  ton: NotisTon;
  text: string;
  detalj?: string;
  /** Visas som knappen "Ångra" i notisen. */
  angra?: () => void;
  /** Millisekunder; fel stannar tills de stängs. */
  tid?: number;
};

const lyssnare = new Set<(n: Notis) => void>();
let nr = 0;

export function notera(text: string, ton: NotisTon = "ok", extra: Omit<Partial<Notis>, "text" | "ton"> = {}) {
  const n: Notis = { id: ++nr, ton, text, ...extra };
  lyssnare.forEach((f) => f(n));
}

export const bbNotis = {
  subscribe(f: (n: Notis) => void) {
    lyssnare.add(f);
    return () => {
      lyssnare.delete(f);
    };
  },
};
