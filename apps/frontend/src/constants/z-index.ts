// apps/frontend/src/constants/z-index.ts
// Canonical z-index hierarchy — ALL components must import from here.
// See: docs/superpowers/specs/2026-03-14-community-intelligence-implementation-design.md § 4.2

export const Z = {
  // Content layer (0-49)
  stickyHeader: 40,
  liveNavPanel: 45,

  // Navigation layer (50)
  nav: 50,

  // Map overlay layer (60-100)
  mapControls: 60,
  mapLoading: 90,
  mapHeader: 100,

  // Bot/companion layer (155-160)
  botTooltip: 155,
  botCompanion: 160,

  // AI chatbot layer (170-180)
  aiFab: 170,
  aiPanel: 180,

  // Modal layer (200+)
  modal: 200,
  mapPicker: 210,       // Intentionally above modals — opens from inside Sheet
  mapPickerPanel: 211,

  // Overlay layer (300)
  fullscreenPanel: 300,

  // System layer (9999)
  toast: 9999,
} as const;
