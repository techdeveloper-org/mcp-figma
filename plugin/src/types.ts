/**
 * Metadata block embedded in every design_spec.json, describing the generator
 * provenance, model version, creation timestamp, and schema version string.
 */
export interface Metadata {
  generated_by: string;
  model: string;
  timestamp: string;
  schema_version: string;
}

/**
 * Typography specification for a single named text style, covering font
 * family, numeric point size, and the standard CSS numeric font-weight scale.
 */
export interface TypographySpec {
  fontFamily: string;
  fontSize: number;
  fontWeight: 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900;
}

/**
 * Design system tokens: hex color map, named typography styles, and a
 * spacing scale expressed as an ordered list of numeric pixel values.
 */
export interface DesignSystem {
  colors: Record<string, string>;
  typography: Record<string, TypographySpec>;
  spacing: number[];
}

/**
 * Padding specification for all four sides of a component, expressed in
 * pixels. All values must be non-negative.
 */
export interface PaddingSpec {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/**
 * A reusable UI component definition. When variants are provided and their
 * count exceeds one, a Figma ComponentSet is created; otherwise a single
 * ComponentNode is used.
 */
export interface Component {
  name: string;
  variants?: string[];
  layout?: 'horizontal' | 'vertical';
  padding?: PaddingSpec;
}

/**
 * A top-level application screen. Each screen maps to one Figma Page.
 * fr_coverage lists the requirement identifiers (e.g. "FR-001") satisfied
 * by this screen, and components lists names of Component entries that
 * should be placed inside the screen's root frame.
 */
export interface Screen {
  name: string;
  fr_coverage: string[];
  width: number;
  height: number;
  components: string[];
}

/**
 * Root document shape for design_spec.json. All fields are required and
 * validated against plugin/schema/design_spec.schema.json before any
 * Figma API call is made.
 */
export interface DesignSpec {
  _metadata: Metadata;
  project: string;
  design_system: DesignSystem;
  screens: Screen[];
  components: Component[];
}

/** Minimal frame descriptor included in the plugin completion summary. */
export interface FrameEntry {
  name: string;
  id: string;
}

/** Minimal page descriptor included in the plugin completion summary. */
export interface PageEntry {
  name: string;
  id: string;
  frames: FrameEntry[];
}

/**
 * Completion summary posted back to the UI and intended to be saved by the
 * developer as docs/phase-3-design/figma_file.md for downstream reference.
 */
export interface PluginCompletionSummary {
  file_key: string;
  pages: PageEntry[];
}

/**
 * Union of all message types the plugin sandbox accepts from the UI iframe.
 * Only messages matching one of these discriminated shapes are processed.
 */
export type MessageToPlugin =
  | { type: 'import-spec'; payload: string }
  | { type: 'close' };

/**
 * Union of all message types the plugin sandbox sends to the UI iframe.
 * Progress messages are fired once per screen; complete is fired exactly
 * once on success; error is fired on any validation or runtime failure.
 */
export type MessageToUI =
  | { type: 'progress'; screen: string; total: number; current: number }
  | { type: 'complete'; summary: PluginCompletionSummary }
  | { type: 'error'; message: string };
