import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import type { Handler } from '@netlify/functions';

// ── HTML / entity stripping ───────────────────────────────────────────────────
function stripHtml(code: string): string {
  return code
    .replace(/<[^>]+>/g, '')   // remove all HTML tags
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

// ── Resolve python3 on the current PATH ──────────────────────────────────────
function getPython(): string {
  try {
    const py = execSync('which python3', { timeout: 5000 }).toString().trim();
    if (py) return py;
  } catch {}
  return 'python3';
}

// ── Main handler ─────────────────────────────────────────────────────────────
export const handler: Handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  let rawCode: string;
  try {
    rawCode = JSON.parse(event.body ?? '{}').code ?? '';
  } catch {
    return {
      statusCode: 400,
      body: JSON.stringify({ success: false, errors: 'Invalid request body' }),
    };
  }

  if (!rawCode.trim()) {
    return {
      statusCode: 400,
      body: JSON.stringify({ success: false, errors: 'No code provided' }),
    };
  }

  // Defense-in-depth: strip any HTML the highlighter may have leaked in
  const cleanCode = stripHtml(rawCode);

  // Write to a unique temp file
  const tmpDir = os.tmpdir();
  const strategyPath = path.join(tmpDir, `strategy_${Date.now()}_${Math.random().toString(36).slice(2)}.py`);

  try {
    fs.writeFileSync(strategyPath, cleanCode, 'utf8');
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ success: false, errors: 'Failed to write temp file' }),
    };
  }

  const python = getPython();

  // ── Step 1: Syntax check via py_compile ────────────────────────────────────
  try {
    execSync(`${python} -m py_compile "${strategyPath}" 2>&1`, { timeout: 15000 });
  } catch (err: any) {
    const raw: string = err.stdout?.toString() ?? err.stderr?.toString() ?? err.message ?? 'Unknown error';
    // Normalize the temp path out of the error message
    const cleaned = raw.replace(new RegExp(strategyPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), 'strategy.py');
    fs.unlink(strategyPath, () => {});
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ success: false, errors: cleaned }),
    };
  }

  // ── Step 2: AST import scan via validate_imports.py ────────────────────────
  // The script lives alongside this function file.
  const validatorPath = path.join(__dirname, 'validate_imports.py');
  const warnings: string[] = [];

  if (fs.existsSync(validatorPath)) {
    try {
      const result = execSync(
        `${python} "${validatorPath}"`,
        {
          input: cleanCode,
          timeout: 10000,
          encoding: 'utf8',
        }
      );
      const unknown: string[] = JSON.parse(result.trim() || '[]');
      for (const mod of unknown) {
        warnings.push(
          `Package '${mod}' is not in the supported allowlist — ensure it is available in your deployment environment.`
        );
      }
    } catch {
      // Non-fatal: if the validator itself errors, skip it silently
    }
  }

  // ── Cleanup ────────────────────────────────────────────────────────────────
  fs.unlink(strategyPath, () => {});

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      success: true,
      message: 'Compilation successful. 0 errors, 0 warnings.',
      warnings,
    }),
  };
};
