/* Minimal line-icon set — 24px grid, 1.6 stroke, inherits currentColor. */
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 16, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const Icon = {
  today: (p: P) => (
    <Svg {...p}>
      <path d="M3 10.5 12 4l9 6.5" />
      <path d="M5 9.5V20h14V9.5" />
      <path d="M9.5 20v-5h5v5" />
    </Svg>
  ),
  idea: (p: P) => (
    <Svg {...p}>
      <path d="M9 18h6" />
      <path d="M10 21h4" />
      <path d="M12 3a6 6 0 0 0-3.6 10.8c.5.4.8.9.9 1.5l.1.7h5.2l.1-.7c.1-.6.4-1.1.9-1.5A6 6 0 0 0 12 3Z" />
    </Svg>
  ),
  compass: (p: P) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" />
    </Svg>
  ),
  mail: (p: P) => (
    <Svg {...p}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </Svg>
  ),
  inbox: (p: P) => (
    <Svg {...p}>
      <path d="M3 12h5l1.5 3h5L16 12h5" />
      <path d="M5 5h14l2 7v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5l2-7Z" />
    </Svg>
  ),
  folder: (p: P) => (
    <Svg {...p}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    </Svg>
  ),
  sparkle: (p: P) => (
    <Svg {...p}>
      <path d="M12 3v3M12 18v3M5 12H2M22 12h-3M6 6l1.6 1.6M16.4 16.4 18 18M18 6l-1.6 1.6M7.6 16.4 6 18" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  ),
  sync: (p: P) => (
    <Svg {...p}>
      <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />
    </Svg>
  ),
  plus: (p: P) => (
    <Svg {...p}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  ),
  send: (p: P) => (
    <Svg {...p}>
      <path d="M22 2 11 13M22 2 15 22l-4-9-9-4 20-7Z" />
    </Svg>
  ),
  check: (p: P) => (
    <Svg {...p}>
      <path d="M20 6 9 17l-5-5" />
    </Svg>
  ),
  arrow: (p: P) => (
    <Svg {...p}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Svg>
  ),
  external: (p: P) => (
    <Svg {...p}>
      <path d="M14 5h5v5M19 5l-8 8M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5" />
    </Svg>
  ),
  bell: (p: P) => (
    <Svg {...p}>
      <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </Svg>
  ),
  star: (p: P) => (
    <Svg {...p}>
      <path d="m12 3 2.6 5.6L21 9.5l-4.5 4.3L17.6 21 12 17.8 6.4 21l1.1-7.2L3 9.5l6.4-.9L12 3Z" />
    </Svg>
  ),
  feed: (p: P) => (
    <Svg {...p}>
      <path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16" />
      <circle cx="5" cy="19" r="1.5" />
    </Svg>
  ),
  zap: (p: P) => (
    <Svg {...p}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </Svg>
  ),
  x: (p: P) => (
    <Svg {...p}>
      <path d="M18 6 6 18M6 6l12 12" />
    </Svg>
  ),
  gear: (p: P) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1M18.4 18.4l-2.1-2.1M7.7 7.7 5.6 5.6" />
    </Svg>
  ),
  sun: (p: P) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4" />
    </Svg>
  ),
  moon: (p: P) => (
    <Svg {...p}>
      <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.5 6.5 0 0 0 9.8 9.8Z" />
    </Svg>
  ),
  ticket: (p: P) => (
    <Svg {...p}>
      <path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2 2 2 0 0 0 0 4 2 2 0 0 1-2 2H5a2 2 0 0 1-2-2 2 2 0 0 0 0-4Z" />
      <path d="M14 7v2M14 13v2" />
    </Svg>
  ),
  pin: (p: P) => (
    <Svg {...p}>
      <path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10Z" />
      <circle cx="12" cy="11" r="2.2" />
    </Svg>
  ),
  search: (p: P) => (
    <Svg {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Svg>
  ),
  book: (p: P) => (
    <Svg {...p}>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z" />
      <path d="M4 19a2 2 0 0 1 2-2h13" />
    </Svg>
  ),
  brain: (p: P) => (
    <Svg {...p}>
      <circle cx="6" cy="7" r="2.4" />
      <circle cx="17" cy="6" r="2.4" />
      <circle cx="18" cy="16" r="2.4" />
      <circle cx="8" cy="17" r="2.4" />
      <path d="M8 8.5 15 7M8.3 15.3 15.6 8M9.6 16.8 15.8 16M7 9.2 7.2 14.6" />
    </Svg>
  ),
  trash: (p: P) => (
    <Svg {...p}>
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
    </Svg>
  ),
};

export type IconName = keyof typeof Icon;
