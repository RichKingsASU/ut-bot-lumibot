import type { Handler } from '@netlify/functions';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

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
      body: JSON.stringify({ error: 'Invalid JSON body' }),
      headers: { 'Content-Type': 'application/json' },
    };
  }

  if (!code.trim()) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: 'No code provided' }),
      headers: { 'Content-Type': 'application/json' },
    };
  }

  // Write code to a temp file and compile it
  const tmpFile = join(tmpdir(), `strategy_${Date.now()}.py`);
  try {
    writeFileSync(tmpFile, code, 'utf8');

    try {
      execSync(`python3 -m py_compile "${tmpFile}" 2>&1`, { timeout: 10000 });
    } catch (compileErr: unknown) {
      const errMsg = compileErr instanceof Error ? compileErr.message : String(compileErr);
      // Clean up error message — strip temp file path
      const cleaned = errMsg.replace(new RegExp(tmpFile.replace(/\\/g, '\\\\'), 'g'), 'strategy.py');
      return {
        statusCode: 200,
        body: JSON.stringify({ success: false, errors: cleaned }),
        headers: { 'Content-Type': 'application/json' },
      };
    }

    // Basic Lumibot API check — look for required class structure
    const warnings: string[] = [];
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
        message: `Compilation successful. 0 errors, ${warnings.length} warning${warnings.length !== 1 ? 's' : ''}.`
      }),
      headers: { 'Content-Type': 'application/json' },
    };
  } finally {
    try { unlinkSync(tmpFile); } catch { /* ignore cleanup errors */ }
  }
};

export { handler };
