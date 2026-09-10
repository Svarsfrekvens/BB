import { useEffect } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { bbNotis } from "@/lib/bb/notis";

/** Visar återkoppling nere till höger. Fel stannar tills de stängs. */
export function Notiser() {
  useEffect(
    () =>
      bbNotis.subscribe((n) => {
        const val = {
          description: n.detalj,
          duration: n.tid ?? (n.ton === "fel" ? Infinity : n.angra ? 10000 : 4000),
          action: n.angra ? { label: "Ångra", onClick: () => n.angra?.() } : undefined,
        };
        if (n.ton === "fel") toast.error(n.text, val);
        else if (n.ton === "info") toast(n.text, val);
        else toast.success(n.text, val);
      }),
    [],
  );
  return <Toaster position="bottom-right" richColors closeButton />;
}
