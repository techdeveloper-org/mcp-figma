/**
 * Design Spec Importer — main plugin entry point.
 *
 * This module is the Figma plugin sandbox code. It has ZERO external network
 * access. All side-effects are performed exclusively through the figma.* API.
 *
 * Message flow:
 *   UI iframe → postMessage → onmessage handler → importSpec() → figma.* calls
 *   importSpec() → figma.ui.postMessage → UI iframe
 *
 * Contracts enforced before any figma.* call:
 *   1. Payload byte length must not exceed MAX_SPEC_BYTES (1 MB).
 *   2. JSON.parse() is wrapped in try/catch; a malformed JSON error is returned
 *      to the UI immediately.
 *   3. The parsed value is validated against the design_spec JSON Schema via
 *      validateDesignSpec(); a schema violation error is returned to the UI.
 *   4. postMessage origin is checked against the Figma sandbox allowlist before
 *      any message content is inspected.
 */
import { validateDesignSpec } from './schema';
import { buildTokens } from './builders/token-builder';
import { buildPages } from './builders/page-builder';
import { buildFrame } from './builders/frame-builder';
import { buildComponent } from './builders/component-builder';
import { buildFrameAnnotation } from './builders/comment-builder';
import type {
  DesignSpec,
  MessageToPlugin,
  MessageToUI,
  PluginCompletionSummary,
} from './types';

/**
 * Maximum accepted payload character count. Figma plugin sandbox has no DOM
 * APIs (no TextEncoder), so we bound by character count. JSON is mostly ASCII
 * (1 byte/char in UTF-8), so 1,048,576 characters ≈ 1 MB upper bound.
 */
const MAX_SPEC_CHARS = 1_048_576; // ~1 MB for ASCII-dominant JSON

figma.showUI(__html__, { width: 480, height: 600, title: 'Design Spec Importer' });

/**
 * Handles incoming messages from the plugin UI iframe.
 *
 * Performs origin validation before inspecting any message content. Only
 * 'import-spec' and 'close' message types are processed; unknown types are
 * silently ignored.
 *
 * @param rawMsg - The raw message value received from the iframe.
 * @param props - Message metadata including the origin URL string.
 */
figma.ui.onmessage = (rawMsg: unknown, props: OnMessageProperties): void => {
  // Accept messages only from the Figma plugin sandbox (origin === 'null') or
  // from the Figma web app origin. Any other origin is silently dropped.
  if (props.origin !== 'null' && !props.origin.startsWith('https://www.figma.com')) {
    return;
  }

  const msg = rawMsg as MessageToPlugin;

  if (msg.type === 'close') {
    figma.closePlugin();
    return;
  }

  if (msg.type === 'import-spec') {
    void importSpec(msg.payload);
  }
};

/**
 * Orchestrates the full import pipeline for a raw JSON string.
 *
 * Steps executed in order:
 *   1. Size guard — rejects payloads exceeding MAX_SPEC_BYTES.
 *   2. JSON.parse() in a try/catch — returns error on malformed input.
 *   3. Schema validation via validateDesignSpec() — returns error on invalid shape.
 *   4. Design token creation (variable collections).
 *   5. Per-screen page creation, frame creation, component placement, annotation.
 *   6. Completion summary posted back to the UI.
 *
 * @param rawJson - The raw JSON string submitted by the user in the UI textarea.
 */
async function importSpec(rawJson: string): Promise<void> {
  try {
    if (rawJson.length > MAX_SPEC_CHARS) {
      sendToUI({
        type: 'error',
        message: 'design_spec.json exceeds 1MB size limit. Please reduce spec size.',
      });
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawJson);
    } catch (parseErr) {
      sendToUI({ type: 'error', message: `Invalid JSON: ${String(parseErr)}` });
      return;
    }

    try {
      validateDesignSpec(parsed);
    } catch (validationErr) {
      sendToUI({ type: 'error', message: String(validationErr) });
      return;
    }

    const spec = parsed as DesignSpec;

    buildTokens(spec.design_system);

    const summary: PluginCompletionSummary = {
      file_key: figma.fileKey ?? 'unknown',
      pages: [],
    };

    const pageResults = buildPages(spec.screens);
    const total = spec.screens.length;
    let current = 0;

    for (const { screen, page } of pageResults) {
      figma.currentPage = page;
      sendToUI({ type: 'progress', screen: screen.name, total, current: ++current });

      const { frame } = buildFrame(screen);

      for (const componentName of screen.components) {
        const componentDef = spec.components.find(c => c.name === componentName);
        if (componentDef !== undefined) {
          const { node } = buildComponent(componentDef);
          frame.appendChild(node);
        }
      }

      buildFrameAnnotation(frame, screen);

      summary.pages.push({
        name: page.name,
        id: page.id,
        frames: [{ name: frame.name, id: frame.id }],
      });
    }

    sendToUI({ type: 'complete', summary });
  } catch (err) {
    sendToUI({ type: 'error', message: `Unexpected error: ${String(err)}` });
  }
}

/**
 * Posts a typed message to the plugin UI iframe.
 *
 * @param msg - A discriminated union value conforming to MessageToUI.
 */
function sendToUI(msg: MessageToUI): void {
  figma.ui.postMessage(msg);
}
