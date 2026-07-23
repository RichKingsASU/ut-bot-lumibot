const { spawn } = require('child_process');

const proc = spawn('npx.cmd', ['-y', '@supabase/mcp-server-supabase@latest', '--access-token', 'sbp_b5ed49872140bb02c41fd72fc955079ade76cd1c', '--project-ref', 'wnigkahkamoizjpmpuxs'], { stdio: ['pipe', 'pipe', 'inherit'], shell: true });

proc.stdout.on('data', (data) => {
    const lines = data.toString().split('\n').filter(Boolean);
    for (const line of lines) {
        if (!line.includes('jsonrpc')) continue;
        console.log('RECV:', line);
    }
});

let msgId = 1;
function sendMsg(msg) {
    msg.jsonrpc = '2.0';
    msg.id = msgId++;
    console.log('SEND:', JSON.stringify(msg));
    proc.stdin.write(JSON.stringify(msg) + '\n');
}

sendMsg({
    method: 'initialize',
    params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'test', version: '1.0' }
    }
});

setTimeout(() => {
    sendMsg({
        method: 'notifications/initialized'
    });
    
    sendMsg({
        method: 'tools/call',
        params: {
            name: 'execute_sql',
            arguments: {
                query: "SELECT to_regclass('public.telegram_outbox'); SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'telegram_outbox'; SELECT policyname, roles, cmd, qual, with_check FROM pg_policies WHERE tablename = 'telegram_outbox'; SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version DESC LIMIT 20;"
            }
        }
    });
}, 3000);

setTimeout(() => proc.kill(), 6000);
