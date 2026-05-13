import { handler } from './dashboard/netlify/functions/alpaca-account.ts';

async function test() {
    console.log("Testing alpaca-account function logic...");

    // Mock event
    const event = {
        httpMethod: 'POST',
        headers: {
            'x-admin-api-key': 'test-admin-key'
        },
        body: JSON.stringify({
            apiKey: 'fake-key',
            apiSecret: 'fake-secret',
            baseUrl: 'https://paper-api.alpaca.markets'
        })
    };

    // We need to mock process.env for the handler if needed, 
    // but the handler uses overrides from the body.
    process.env.ADMIN_API_KEY = 'test-admin-key';

    try {
        const result = await handler(event, {});
        console.log("Result Status:", result.statusCode);
        console.log("Result Body:", result.body);
    } catch (e) {
        console.error("Test failed:", e);
    }
}

test();
