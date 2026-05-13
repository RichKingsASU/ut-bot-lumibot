import type { Handler } from '@netlify/functions';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, existsSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const VENV_PATH = '/tmp/strategy-venv';
const REQUIREMENTS = [
  'pandas>=2.0.0,<3.0.0',
  'numpy>=1.24.0,<2.0.0',
  'lumibot>=4.4.56',
  'alpaca-trade-api>=3.0.0',
  'ta>=0.10.0',
];

function stripHtmlFromCode(code: string): string {
  return code
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function ensureVenv(): string | null {
  try {
    if (!existsSync(`${VENV_PATH}/bin/python`)) {
      execSync(`python3 -m venv ${VENV_PATH}`, { timeout: 30000 });
      execSync(
        `${VENV_PATH}/bin/pip install --quiet --disable-pip-version-check ${REQUIREMENTS.join(' ')}`,
        { timeout: 120000 }
      );
    }
    return null;
  } catch (err: unknown) {
    return err instanceof Error ? err.message : String(err);
  }
}

const handler: Handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method not allowed' }),
      headers: { 'Content-Type': 'application/json' },
    };
  }

  let code: string;
  try {
    const body = JSON.parse(event.body || '{}');
    code = body.code || '';
  } catch {
    return {
      statusCode: 400,
      body: JSON.stringify({ success: false, errors: 'Invalid request body' }),
      headers: { 'Content-Type': 'application/json' },
    };
  }

  if (!code.trim()) {
    return {
      statusCode: 400,
      body: JSON.stringify({ success: false, errors: 'No code provided' }),
      headers: { 'Content-Type': 'application/json' },
    };
  }

  code = stripHtmlFromCode(code);

  const strategyPath = join(tmpdir(), `strategy_${Date.now()}.py`);

  try {
    writeFileSync(strategyPath, code, 'utf8');

    const venvErr = ensureVenv();
    const pythonBin = venvErr ? 'python3' : `${VENV_PATH}/bin/python`;

    try {
      execSync(`${pythonBin} -m py_compile "${strategyPath}" 2>&1`, { timeout: 30000 });
    } catch (compileErr: unknown) {
      const raw =
        (compileErr as { stdout?: Buffer })?.stdout?.toString() ||
        (compileErr as { stderr?: Buffer })?.stderr?.toString() ||
        (compileErr instanceof Error ? compileErr.message : String(compileErr));
      const cleaned = raw.replace(new RegExp(strategyPath.replace(/\\/g, '\\\\'), 'g'), 'strategy.py');
      return {
        statusCode: 200,
        body: JSON.stringify({ success: false, errors: cleaned }),
        headers: { 'Content-Type': 'application/json' },
      };
    }

    const warnings: string[] = [];

    if (!venvErr) {
      const importLines = code
        .split('\n')
        .filter((l) => l.trim().startsWith('import ') || l.trim().startsWith('from '))
        .slice(0, 20)
        .join('\n');

      if (importLines) {
        try {
          execSync(`${pythonBin} -c "${importLines.replace(/"/g, '\\"')}" 2>&1`, { timeout: 20000 });
        } catch (importErr: unknown) {
          const out =
            (importErr as { stdout?: Buffer })?.stdout?.toString() ||
            (importErr as { stderr?: Buffer })?.stderr?.toString() ||
            (importErr instanceof Error ? importErr.message : 'Unknown import issue');
          warnings.push(`Import warning: ${out.split('\n').filter(Boolean).pop() || 'Unknown import issue'}`);
        }
      }
    } else {
      warnings.push(`Venv bootstrap skipped: ${venvErr.split('\n')[0]}`);
    }

    if (!code.includes('Strategy')) {
      warnings.push('Warning: No Strategy class detected. Ensure your class extends lumibot Strategy.');
    }
    if (!code.includes('initialize') && !code.includes('on_trading_iteration')) {
      warnings.push('Warning: No initialize() or on_trading_iteration() method found.');
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        warnings,
        message: `Compilation successful. 0 errors, ${warnings.length} warning${warnings.length !== 1 ? 's' : ''}.`,
      }),
      headers: { 'Content-Type': 'application/json' },
    };
  } finally {
    try {
      unlinkSync(strategyPath);
    } catch {
      /* ignore cleanup errors */
    }
  }
};

export { handler };
