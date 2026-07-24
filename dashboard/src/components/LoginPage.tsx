import React, { useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import { motion } from 'framer-motion';
import { Lock, Mail, Activity, Shield, ArrowRight, Zap } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Test user local bypass
    if (email === 'test@disruptingalpha.com' && password === 'admin123') {
      localStorage.setItem('DEV_BYPASS_AUTH', 'true');
      window.location.reload();
      return;
    }

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[var(--color-bg-space)] text-vibrant font-sans flex overflow-hidden relative selection:bg-blue-500/30">
      {/* Background Grid & Effects */}
      <div className="absolute inset-0 bg-grid opacity-[0.15] z-0 pointer-events-none" />
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-600/20 rounded-full blur-[120px] -translate-y-1/2 z-0 pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[100px] translate-y-1/3 z-0 pointer-events-none mix-blend-screen" />

      {/* Left Branding Panel */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 z-10 relative border-r border-white/5">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="flex items-center gap-4"
        >
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 p-[1px] shadow-glow-blue">
            <div className="w-full h-full bg-black rounded-xl flex items-center justify-center">
              <Activity className="w-6 h-6 text-cyan-400" />
            </div>
          </div>
          <span className="text-xl font-bold tracking-widest uppercase text-gradient-blue">
            Disrupting Alpha
          </span>
        </motion.div>

        <div className="max-w-md">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
          >
            <h1 className="text-5xl font-extrabold tracking-tight mb-6 leading-[1.1]">
              Institutional <br/>
              <span className="text-gradient-blue">Intelligence</span> <br/>
              Terminal
            </h1>
            <p className="text-dim text-lg leading-relaxed mb-8 font-medium">
              Advanced quantitative trading orchestration. Secure, real-time access to your alpha generation engine.
            </p>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.6 }}
            className="flex gap-4"
          >
            <div className="glass-panel p-4 flex-1 flex flex-col gap-2">
              <Shield className="w-5 h-5 text-emerald-400" />
              <span className="text-xs text-dim uppercase tracking-wider font-bold">Security</span>
              <span className="text-sm font-medium">Enterprise Grade</span>
            </div>
            <div className="glass-panel p-4 flex-1 flex flex-col gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              <span className="text-xs text-dim uppercase tracking-wider font-bold">Latency</span>
              <span className="text-sm font-medium">Ultra-low ms</span>
            </div>
          </motion.div>
        </div>

        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.8 }}
          className="text-xs text-dim font-mono"
        >
          SYSTEM.VERSION: 2.4.0-STABLE <br/>
          CONNECTION: ENCRYPTED WSS
        </motion.div>
      </div>

      {/* Right Login Panel */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 z-10 relative">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="w-full max-w-md glass-panel p-8 md:p-10"
        >
          <div className="mb-8 text-center lg:text-left">
            <h2 className="text-2xl font-bold mb-2">Welcome Back</h2>
            <p className="text-dim text-sm">Enter your operator credentials to securely connect.</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-1.5 text-left">
              <label className="text-[11px] font-bold text-secondary uppercase tracking-widest pl-1">
                Operator Email
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-dim group-focus-within:text-blue-400 transition-colors">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@disruptingalpha.com"
                  required
                  className="w-full bg-[var(--color-surface-1)] border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-vibrant placeholder:text-dim focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all shadow-inner"
                />
              </div>
            </div>

            <div className="space-y-1.5 text-left">
              <label className="text-[11px] font-bold text-secondary uppercase tracking-widest pl-1">
                Password
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-dim group-focus-within:text-blue-400 transition-colors">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  className="w-full bg-[var(--color-surface-1)] border border-white/10 rounded-xl py-3 pl-10 pr-4 text-sm text-vibrant placeholder:text-dim focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all shadow-inner"
                />
              </div>
            </div>

            {error && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-sm flex items-start gap-2"
              >
                <Shield className="w-4 h-4 mt-0.5 shrink-0" />
                <span className="leading-tight">{error}</span>
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="button-primary w-full group flex items-center justify-center gap-2 mt-2 py-3.5"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </div>
              ) : (
                <>
                  <span>Initialize Session</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-white/5 text-center flex flex-col gap-2">
            <p className="text-[11px] text-dim font-medium uppercase tracking-widest">
              Secured by Supabase Auth
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
};
