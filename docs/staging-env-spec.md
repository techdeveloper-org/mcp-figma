# Staging Environment Specification — Figma Plugin

## Test Figma File Setup

Create a dedicated test Figma file:
- **Name**: `Design Spec Importer — Test File`
- **Location**: Team workspace (not personal drafts)
- **Access**: Team members with Developer role minimum

Do NOT use any production Figma file for tests.

## Required GitHub Repository Secrets

| Secret Name | Description | Scope |
|-------------|-------------|-------|
| `FIGMA_TEST_ACCESS_TOKEN` | Figma Personal Access Token for CI | files:read, variables:read, variables:write |
| `FIGMA_TEST_FILE_KEY` | Key of dedicated test Figma file | From Figma URL: `figma.com/file/{KEY}/...` |

**To set secrets**: GitHub repo → Settings → Secrets and variables → Actions → New repository secret

## Secret Rotation Policy (CERT-In Direction 1 Compliance)

Figma Personal Access Tokens expire every **90 days**. Rotation procedure:

1. **Day 0**: Generate new Figma PAT at figma.com → Account Settings → Personal Access Tokens
2. **Day 0**: Update `FIGMA_TEST_ACCESS_TOKEN` in GitHub Actions secrets
3. **Day 0**: Run `npm run test` locally to verify new token works
4. **Day 0**: Revoke old token at figma.com
5. Set calendar reminder for Day +90

Rotation must complete within 24 hours of token expiry (CERT-In Direction 1 §4(a): credential rotation within defined policy period).

## NEVER

- Hardcode any token in source code
- Use `process.env` in plugin source files
- Commit `.env` files to repository
- Use production Figma file key in CI

## Environment Verification

Run before CI pipeline:
```bash
cd plugin && npm ci && npm run typecheck && npm run build
```

Expected: TypeScript check passes, `dist/code.js` created with no errors.
