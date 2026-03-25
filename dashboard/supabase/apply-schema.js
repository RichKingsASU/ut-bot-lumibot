import pg from 'pg';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { Client } = pg;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sqlPath = path.join(__dirname, 'schema.sql');
const sql = fs.readFileSync(sqlPath, 'utf8');

const client = new Client({
  host: 'wnigkahkamoizjpmpuxs.supabase.co',
  port: 6543,
  user: 'postgres.wnigkahkamoizjpmpuxs',
  password: 'Pp7E8vgJblQyNicB',
  database: 'postgres',
});

async function main() {
  try {
    console.log('Connecting to Supabase...');
    await client.connect();
    console.log('Connected. Executing SQL...');
    
    // Split SQL into parts if needed, or just run as one block
    // pg-node can handle multiple statements in one query call
    await client.query(sql);

    // Note: The comments at the bottom of schema.sql (extensions) 
    // were excluded from the main execution block in my previous write_to_file 
    // unless they were uncommented. Let me check the file content.
    
    console.log('SQL Executed Successfully.');
  } catch (err) {
    console.error('Execution Failed:', err);
  } finally {
    await client.end();
  }
}

main();
