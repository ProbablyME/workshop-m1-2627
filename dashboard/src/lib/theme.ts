import { useEffect, useState } from "react";

export type Mode = "light" | "dark";

// Palette de référence du guide dataviz : les mêmes teintes, pas de pas différents selon le mode.
// Série 1 bleu = température, série 3 aqua = humidité, série 2 orange = gaz. Statuts fixes.
export interface Palette {
  temp: string; hum: string; gas: string;
  surface: string; grid: string; axis: string; muted: string; ink: string;
  good: string; warning: string; serious: string; critical: string;
}

export const palette: Record<Mode, Palette> = {
  light: {
    temp: "#2a78d6", hum: "#1baf7a", gas: "#eb6834",
    surface: "#fcfcfb", grid: "#e1e0d9", axis: "#c3c2b7", muted: "#898781", ink: "#0b0b0b",
    good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b",
  },
  dark: {
    temp: "#3987e5", hum: "#199e70", gas: "#d95926",
    surface: "#1a1a19", grid: "#2c2c2a", axis: "#383835", muted: "#898781", ink: "#ffffff",
    good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b",
  },
};

const KEY = "sx-theme";

function systemMode(): Mode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useMode(): [Mode, () => void] {
  const [mode, setMode] = useState<Mode>(() => {
    // ?theme=dark|light force le thème (captures d'écran, démo sur écran du jury)
    const forced = new URLSearchParams(location.search).get("theme");
    if (forced === "light" || forced === "dark") return forced;
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* stockage indisponible */
    }
    return systemMode();
  });

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
  }, [mode]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      try {
        if (!localStorage.getItem(KEY)) setMode(systemMode());
      } catch {
        setMode(systemMode());
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    setMode((m) => {
      const next: Mode = m === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, next);
      } catch {
        /* ignore */
      }
      return next;
    });
  };
  return [mode, toggle];
}
