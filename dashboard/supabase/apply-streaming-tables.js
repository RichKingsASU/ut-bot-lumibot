import pg from 'pg';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { Client } = pg;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sqlPath = path.join(__dirname, 'migrations', '20260326000000_streaming_tables.sql');
const sql = fs.readFileSync(sqlPath, 'utf8');

const client = new Client({
  host: 'wnigkahkamoizjpmpuxs.supabase.co',
  port: 5432,
  user: 'postgres.wnigkahkamoizjpmpuxs',
  password: 'Pp7E8vgJblQyNicB',
  database: 'postgres',
  ssl: { rejectUnauthorized: false },
});

async function main() {
  try {
    console.log('Connecting to Supabase...');
    await client.connect();
    console.log('Connected. Creating streaming tables...');

    await client.query(sql);

    console.log('Streaming tables created successfully.');
  } catch (err) {
    console.error('Execution Failed:', err);
    process.exit(1);
  } finally {
    await client.end();
  }
}

main();
