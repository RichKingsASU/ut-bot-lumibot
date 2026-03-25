import pg from 'pg';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { Client } = pg;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sqlPath = path.join(__dirname, 'migrations', '20260325000000_8_screen_upgrade.sql');
const sql = fs.readFileSync(sqlPath, 'utf8');

const client = new Client({
  host: 'wnigkahkamoizjpmpuxs.supabase.co',
  port: 5432,
  user: 'postgres.wnigkahkamoizjpmpuxs',
  password: 'Pp7E8vgJblQyNicB',
  database: 'postgres',
});

async function main() {
  try {
    console.log('Connecting to Supabase (Port 6543)...');
    await client.connect();
    console.log('Connected. Executing upgrade SQL...');
    
    await client.query(sql);

    console.log('8-Screen Upgrade SQL Executed Successfully.');
  } catch (err) {
    console.error('Execution Failed:', err);
    process.exit(1);
  } finally {
    await client.end();
  }
}

main();
