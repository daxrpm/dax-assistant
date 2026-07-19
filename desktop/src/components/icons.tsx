/**
 * 16px stroked glyphs, drawn inline.
 *
 * Inline rather than an icon package: the set is tiny, and a self-contained
 * webview should not pull a dependency for six paths.
 */

interface IconProps {
  size?: number;
}

function Svg({ size = 16, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const ChatIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.5 6.5a3 3 0 0 1 3-3h5a3 3 0 0 1 3 3v2a3 3 0 0 1-3 3H7l-3.5 2.5v-2.6a3 3 0 0 1-1-2.2z" />
  </Svg>
);

export const DashboardIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2.5" y="2.5" width="5" height="5" rx="1.2" />
    <rect x="8.5" y="2.5" width="5" height="5" rx="1.2" />
    <rect x="2.5" y="8.5" width="5" height="5" rx="1.2" />
    <rect x="8.5" y="8.5" width="5" height="5" rx="1.2" />
  </Svg>
);

export const McpIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="4" r="1.8" />
    <circle cx="3.8" cy="11.5" r="1.8" />
    <circle cx="12.2" cy="11.5" r="1.8" />
    <path d="M8 5.8 4.6 9.9M8 5.8l3.4 4.1M5.6 11.5h4.8" />
  </Svg>
);

export const LogsIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 3.5h10M3 6.5h10M3 9.5h7M3 12.5h5" />
  </Svg>
);

export const SettingsIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="8" r="2.2" />
    <path d="M8 1.8v1.6M8 12.6v1.6M14.2 8h-1.6M3.4 8H1.8M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1M12.4 12.4l-1.1-1.1M4.7 4.7 3.6 3.6" />
  </Svg>
);

export const VoiceIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="6" y="2" width="4" height="7" rx="2" />
    <path d="M3.5 7.5a4.5 4.5 0 0 0 9 0M8 12v2" />
  </Svg>
);

export const XIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 4l8 8M12 4l-8 8" />
  </Svg>
);

export const CheckIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 8.5l3 3 6-7" />
  </Svg>
);

export const PlusIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 3.5v9M3.5 8h9" />
  </Svg>
);

export const TrashIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.8 4.5h10.4M6.5 4.5V3a.8.8 0 0 1 .8-.8h1.4a.8.8 0 0 1 .8.8v1.5" />
    <path d="M4.2 4.5l.6 8.2a1 1 0 0 0 1 .9h4.4a1 1 0 0 0 1-.9l.6-8.2" />
  </Svg>
);

export const SearchIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="7.2" cy="7.2" r="4.2" />
    <path d="M10.4 10.4L13.5 13.5" />
  </Svg>
);

export const SendIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13.5 2.5L7.2 8.8M13.5 2.5L9.5 13.5l-2.3-4.7L2.5 6.5z" />
  </Svg>
);

export const SparkleIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 2l1.5 4.5L14 8l-4.5 1.5L8 14l-1.5-4.5L2 8l4.5-1.5z" />
  </Svg>
);

export const WrenchIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.4 2.6a3.6 3.6 0 0 0-4.2 4.7L2.6 10.9a1.4 1.4 0 0 0 2 2l3.6-3.6a3.6 3.6 0 0 0 4.7-4.2l-2 2-1.7-1.7z" />
  </Svg>
);

export const AlertIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="8" r="5.8" />
    <path d="M8 5v3.6M8 10.8v.1" />
  </Svg>
);

export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 1.8l5 1.9v4.1c0 3-2.1 5.4-5 6.4-2.9-1-5-3.4-5-6.4V3.7z" />
    <path d="M8 5.6v3M8 10.6v.1" />
  </Svg>
);

export const ChevronDownIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 6.5L8 10.5l4-4" />
  </Svg>
);

export const ChevronRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.5 4L10.5 8l-4 4" />
  </Svg>
);

export const ActivityIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.8 8h2.8l1.9-5 2.6 10 1.9-5h2.9" />
  </Svg>
);

export const CopyIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="5.5" y="5.5" width="8" height="8" rx="1.4" />
    <path d="M10.5 5.5v-1a1.4 1.4 0 0 0-1.4-1.4H3.9a1.4 1.4 0 0 0-1.4 1.4v5.2a1.4 1.4 0 0 0 1.4 1.4h1" />
  </Svg>
);

export const LinkIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.6 9.4a2.6 2.6 0 0 0 3.9.3l2-2a2.6 2.6 0 1 0-3.7-3.7l-1.1 1.1" />
    <path d="M9.4 6.6a2.6 2.6 0 0 0-3.9-.3l-2 2a2.6 2.6 0 1 0 3.7 3.7l1.1-1.1" />
  </Svg>
);

export const TerminalIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="1.8" y="2.8" width="12.4" height="10.4" rx="1.6" />
    <path d="M4.5 6.5L6.5 8.3 4.5 10.1M8.4 10.4h3.2" />
  </Svg>
);

export const StoreIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.4 6.2L3.4 3h9.2l1 3.2M2.4 6.2h11.2M2.4 6.2v6.2a1 1 0 0 0 1 1h9.2a1 1 0 0 0 1-1V6.2" />
    <path d="M6.2 9.2h3.6" />
  </Svg>
);

export const BrainIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.4 2.6a2.2 2.2 0 0 0-2.2 2.2 2 2 0 0 0-1 3.5 2.2 2.2 0 0 0 1.4 3.6 2.2 2.2 0 0 0 4.2-.9V4.8a2.2 2.2 0 0 0-2.4-2.2z" />
    <path d="M11 5.2a1.8 1.8 0 1 1 1.8 3 1.8 1.8 0 0 1-1.2 3" />
  </Svg>
);

export const RefreshIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13.2 7a5.3 5.3 0 0 0-9.4-2.3M2.8 9a5.3 5.3 0 0 0 9.4 2.3" />
    <path d="M13.4 3.4V7h-3.6M2.6 12.6V9h3.6" />
  </Svg>
);

export const ArrowDownIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 3v9M4.4 8.6L8 12.2l3.6-3.6" />
  </Svg>
);

export const PlayIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 3.4l7 4.6-7 4.6z" />
  </Svg>
);

export const EyeIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.6 8s2.4-4.2 6.4-4.2S14.4 8 14.4 8s-2.4 4.2-6.4 4.2S1.6 8 1.6 8z" />
    <circle cx="8" cy="8" r="1.8" />
  </Svg>
);
