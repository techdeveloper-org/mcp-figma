/**
 * Runtime JSON Schema validator for design_spec.json.
 *
 * Uses AJV with the draft-07 schema compiled once at module load time.
 * The exported validateDesignSpec function acts as a type assertion guard:
 * it throws a descriptive Error when validation fails so callers can relay
 * the message to the UI without performing additional error handling.
 */
import Ajv from 'ajv';
import type { DesignSpec } from './types';

const ajv = new Ajv({ allErrors: true, strict: false });

const designSpecSchema = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  type: 'object',
  required: ['_metadata', 'project', 'design_system', 'screens', 'components'],
  additionalProperties: false,
  properties: {
    _metadata: {
      type: 'object',
      required: ['generated_by', 'model', 'timestamp', 'schema_version'],
      additionalProperties: false,
      properties: {
        generated_by: { type: 'string', minLength: 1 },
        model: { type: 'string', minLength: 1 },
        timestamp: { type: 'string', minLength: 1 },
        schema_version: { type: 'string', pattern: '^\\d+\\.\\d+\\.\\d+$' }
      }
    },
    project: { type: 'string', minLength: 1 },
    design_system: {
      type: 'object',
      required: ['colors', 'typography', 'spacing'],
      additionalProperties: false,
      properties: {
        colors: {
          type: 'object',
          minProperties: 1,
          additionalProperties: { type: 'string', pattern: '^#[0-9A-Fa-f]{6}$' }
        },
        typography: {
          type: 'object',
          additionalProperties: {
            type: 'object',
            required: ['fontFamily', 'fontSize', 'fontWeight'],
            additionalProperties: false,
            properties: {
              fontFamily: { type: 'string', minLength: 1 },
              fontSize: { type: 'number', minimum: 8, maximum: 128 },
              fontWeight: {
                type: 'number',
                enum: [100, 200, 300, 400, 500, 600, 700, 800, 900]
              }
            }
          }
        },
        spacing: {
          type: 'array',
          minItems: 1,
          items: { type: 'number', minimum: 0 }
        }
      }
    },
    screens: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['name', 'fr_coverage', 'width', 'height', 'components'],
        additionalProperties: false,
        properties: {
          name: { type: 'string', minLength: 1 },
          fr_coverage: {
            type: 'array',
            minItems: 1,
            items: { type: 'string', pattern: '^FR-\\d{3}$' }
          },
          width: { type: 'number', minimum: 320, maximum: 1920 },
          height: { type: 'number', minimum: 480, maximum: 1440 },
          components: {
            type: 'array',
            items: { type: 'string' }
          }
        }
      }
    },
    components: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name'],
        additionalProperties: false,
        properties: {
          name: { type: 'string', minLength: 1 },
          variants: {
            type: 'array',
            items: { type: 'string' }
          },
          layout: {
            type: 'string',
            enum: ['horizontal', 'vertical']
          },
          padding: {
            type: 'object',
            required: ['top', 'right', 'bottom', 'left'],
            additionalProperties: false,
            properties: {
              top: { type: 'number', minimum: 0 },
              right: { type: 'number', minimum: 0 },
              bottom: { type: 'number', minimum: 0 },
              left: { type: 'number', minimum: 0 }
            }
          }
        }
      }
    }
  }
};

const validateFn = ajv.compile(designSpecSchema);

/**
 * Validates parsed JSON against the design_spec schema and asserts the
 * TypeScript type DesignSpec on success.
 *
 * @param data - The unknown value returned by JSON.parse().
 * @throws {Error} When schema validation fails, with a semicolon-separated
 *   list of all AJV error messages included in the message string.
 */
export function validateDesignSpec(data: unknown): asserts data is DesignSpec {
  if (!validateFn(data)) {
    // AJV always sets errors when validation fails; the non-null assertion is
    // safe here because validateFn returned false, which guarantees errors.
    const errors = validateFn.errors!;
    // AJV standard validators always populate message; using toString() to
    // satisfy the TypeScript type without introducing an uncovered branch.
    const messages = errors
      .map(e => `${e.instancePath || '/'} ${String(e.message)}`)
      .join('; ');
    throw new Error(`design_spec.json validation failed: ${messages}`);
  }
}
