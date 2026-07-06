import React from 'react';

// Shared SVG icon set. All icons follow the same stroke style; `size` controls
// width/height so call sites can keep their existing pixel dimensions.

const strokeProps = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export const PlusIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const SearchIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <circle cx="11" cy="11" r="7" /><path d="M16.5 16.5 21 21" />
  </svg>
);

export const FolderIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
  </svg>
);

export const SettingsIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);

export const SidebarIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" />
  </svg>
);

export const BookmarkIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M6 3h12v18l-6-4-6 4z" />
  </svg>
);

export const ScalesIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M12 3v18M5 21h14M6 7h12M6 7l-3 7a3 3 0 0 0 6 0z" />
    <path d="M18 7l-3 7a3 3 0 0 0 6 0z" />
  </svg>
);

export const GavelIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M14 3l7 7-4 4-7-7z" />
    <path d="M10 7 3 14l4 4 7-7" />
    <path d="M5 21h10" />
  </svg>
);

export const CalendarIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" />
  </svg>
);

export const PaperclipIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M21 12.5 12.5 21a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 1 1-2.6-2.6l8-8" />
  </svg>
);

export const SlidersIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M3 5h18l-7 9v5l-4 2v-7L3 5z" />
  </svg>
);

export const SendIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M3 12l18-8-8 18-2-8-8-2z" />
  </svg>
);

export const StopIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <rect x="5" y="5" width="14" height="14" rx="2" />
  </svg>
);

export const ChevRightIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M9 6l6 6-6 6" />
  </svg>
);

export const FilterIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M3 5h18l-7 9v5l-4 2v-7L3 5z" />
  </svg>
);

export const ExternalLinkIcon = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M15 3h6v6M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
  </svg>
);

export const ChevronRightIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 18l6-6-6-6" />
  </svg>
);

export const ChevronLeftIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 18l-6-6 6-6" />
  </svg>
);

export const BookIcon = ({ size = 13 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5z" />
    <path d="M20 18v4H6.5A2.5 2.5 0 0 1 4 19.5" />
  </svg>
);

export const CopyIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M6 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" />
  </svg>
);

export const RefreshIcon = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...strokeProps}>
    <path d="M4 12a8 8 0 0 1 14-5.3L21 9" />
    <path d="M21 4v5h-5" />
    <path d="M20 12a8 8 0 0 1-14 5.3L3 15" />
    <path d="M3 20v-5h5" />
  </svg>
);
