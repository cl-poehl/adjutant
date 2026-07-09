"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icons";

type Theme = "dark" | "light";

function apply(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = (localStorage.getItem("ip-theme") as Theme | null) ?? "light";
    setTheme(saved);
    apply(saved);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    apply(next);
    localStorage.setItem("ip-theme", next);
  };

  return (
    <button
      onClick={toggle}
      title={theme === "dark" ? "Switch to light" : "Switch to dark"}
      className="btn btn-ghost h-7 w-7 justify-center p-0"
    >
      {theme === "dark" ? <Icon.sun size={14} /> : <Icon.moon size={14} />}
    </button>
  );
}
