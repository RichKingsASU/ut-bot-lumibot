import { Config, Context } from '@netlify/functions';

export default async (req: Request, context: Context) => {
  console.log('Syncing Alpaca History...');
  // Implementation logic for Alpaca history sync
  return new Response('OK');
};

export const config: Config = {
  schedule: '*/5 * * * *', // Runs every 5 minutes
};
