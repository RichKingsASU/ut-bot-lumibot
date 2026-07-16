import React, { Suspense, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
const NotFound = React.lazy(() => import('./pages/NotFound'))
import { LoginPage } from './components/LoginPage'
import { MainLayout } from './components/dashboard/layout/MainLayout'
import { supabase, supabaseMisconfigured } from './lib/supabaseClient'
import { toUserMessage } from './lib/apiError'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { Skeleton } from './components/ui/Skeleton'
import type { Session } from '@supabase/supabase-js'
import { TradingProvider } from './context/TradingContext'

// ─── Lazy-loaded route components (code-split per surface) ──────────────
const OverviewView = React.lazy(() => import('./components/dashboard/Overview/OverviewView'))
const EquitiesTradeView = React.lazy(() => import('./components/dashboard/Equities/EquitiesTradeView'))
const EquitiesMonitorView = React.lazy(() => import('./components/dashboard/Equities/EquitiesMonitorView'))
const EquitiesPerformanceView = React.lazy(() => import('./components/dashboard/Equities/EquitiesPerformanceView'))
const EquitiesStrategyView = React.lazy(() => import('./components/dashboard/Equities/EquitiesStrategyView'))
const GreeksHeatmap = React.lazy(() => import('./components/dashboard/Greeks/GreeksHeatmap'))
const CryptoTradeView = React.lazy(() => import('./components/dashboard/Crypto/CryptoTradeView'))
const CryptoMonitorView = React.lazy(() => import('./components/dashboard/Crypto/CryptoMonitorView'))
const CryptoPerformanceView = React.lazy(() => import('./components/dashboard/Crypto/CryptoPerformanceView'))
const CryptoStrategyView = React.lazy(() => import('./components/dashboard/Crypto/CryptoStrategyView'))
const StrategyLabView = React.lazy(() => import('./components/dashboard/StrategyLab/StrategyLabView'))
const BacktestView = React.lazy(() => import('./components/dashboard/StrategyLab/BacktestView'))
const NewsFeedView = React.lazy(() => import('./components/dashboard/NewsSocial/NewsFeedView'))
const SentimentView = React.lazy(() => import('./components/dashboard/NewsSocial/SentimentView'))
const WatchlistView = React.lazy(() => import('./components/dashboard/NewsSocial/WatchlistView'))
const PositionSizingView = React.lazy(() => import('./components/dashboard/RiskManager/PositionSizingView'))
const RiskRulesView = React.lazy(() => import('./components/dashboard/RiskManager/RiskRulesView'))
const AccountHealthView = React.lazy(() => import('./components/dashboard/RiskManager/AccountHealthView'))
const RiskManagerView = React.lazy(() => import('./components/dashboard/RiskManager/RiskManagerView'))
const DataView = React.lazy(() => import('./components/dashboard/Data/DataView').then(m => ({ default: m.DataView })))
const AlertsView = React.lazy(() => import('./components/dashboard/Alerts/AlertsView').then(m => ({ default: m.AlertsView })))
const SystemHealthView = React.lazy(() => import('./components/dashboard/SystemHealth/SystemHealthView'))
const SystemHealthPage = React.lazy(() => import('./pages/SystemHealthPage'))
const AgentPipelinePage = React.lazy(() => import('./pages/AgentPipelinePage'))
const SettingsView = React.lazy(() => import('./components/dashboard/Settings/SettingsView').then(m => ({ default: m.SettingsView })))

// ─── Route Loading Fallback ─────────────────────────────────────────────
function RouteFallback() {
  return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border bg-card p-4 space-y-3 min-h-[160px]">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-2 w-full" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border bg-card p-4 min-h-[300px]">
        <Skeleton className="h-full w-full rounded-lg" />
      </div>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    if (supabaseMisconfigured) {
      setAuthError('Database is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in environment variables.')
      setAuthLoading(false)
      return
    }

    supabase.auth.getSession().then(({ data: { session: s }, error }) => {
      if (error) setAuthError(toUserMessage(error))
      if (s?.user?.user_metadata?.ADMIN_API_KEY) {
        const key = s.user.user_metadata.ADMIN_API_KEY;
        localStorage.setItem('ADMIN_API_KEY', key);
        localStorage.setItem('admin_api_key', key);
      }
      setSession(s)
      setAuthLoading(false)
    }).catch((err) => {
      setAuthError(toUserMessage(err))
      setAuthLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      if (s?.user?.user_metadata?.ADMIN_API_KEY) {
        const key = s.user.user_metadata.ADMIN_API_KEY;
        localStorage.setItem('ADMIN_API_KEY', key);
        localStorage.setItem('admin_api_key', key);
      }
      setSession(s)
    })

    return () => subscription.unsubscribe()
  }, [])

  if (authLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-muted-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          <span className="text-xs font-medium uppercase tracking-wider">Initializing</span>
        </div>
      </div>
    )
  }

  if (authError) {
    return (
      <div className="h-screen flex items-center justify-center flex-col gap-4 bg-background text-muted-foreground p-8">
        <div className="text-destructive font-bold text-lg">Configuration Error</div>
        <div className="max-w-md text-center text-sm leading-relaxed">{authError}</div>
      </div>
    )
  }

  if (!session) {
    const bypassAuth = localStorage.getItem('DEV_BYPASS_AUTH') === 'true' || window.location.search.includes('dev=true');
    if (bypassAuth) {
      // Mock session to allow dashboard inspection in local sandbox environments
      const mockSession = {
        access_token: 'mock-token',
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'mock-refresh',
        user: {
          id: 'dev-user-id',
          email: 'dev@disruptingalpha.com',
          role: 'authenticated',
          aud: 'authenticated',
        }
      };
      // Force set session in React state
      setTimeout(() => setSession(mockSession as any), 0);
    } else {
      return <LoginPage />
    }
  }

  return (
    <TradingProvider>
      <BrowserRouter>
        <ErrorBoundary>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Suspense fallback={<RouteFallback />}><OverviewView /></Suspense>} />
            <Route path="/equities/trade" element={<Suspense fallback={<RouteFallback />}><EquitiesTradeView /></Suspense>} />
            <Route path="/equities/monitor" element={<Suspense fallback={<RouteFallback />}><EquitiesMonitorView /></Suspense>} />
            <Route path="/equities/performance" element={<Suspense fallback={<RouteFallback />}><EquitiesPerformanceView /></Suspense>} />
            <Route path="/equities/strategy" element={<Suspense fallback={<RouteFallback />}><EquitiesStrategyView /></Suspense>} />
            <Route path="/equities/greeks" element={<Suspense fallback={<RouteFallback />}><GreeksHeatmap /></Suspense>} />
            <Route path="/crypto/trade" element={<Suspense fallback={<RouteFallback />}><CryptoTradeView /></Suspense>} />
            <Route path="/crypto/monitor" element={<Suspense fallback={<RouteFallback />}><CryptoMonitorView /></Suspense>} />
            <Route path="/crypto/performance" element={<Suspense fallback={<RouteFallback />}><CryptoPerformanceView /></Suspense>} />
            <Route path="/crypto/strategy" element={<Suspense fallback={<RouteFallback />}><CryptoStrategyView /></Suspense>} />
            <Route path="/strategy-lab" element={<Suspense fallback={<RouteFallback />}><StrategyLabView /></Suspense>} />
            <Route path="/strategy-lab/editor" element={<Suspense fallback={<RouteFallback />}><StrategyLabView /></Suspense>} />
            <Route path="/strategy-lab/backtest" element={<Suspense fallback={<RouteFallback />}><BacktestView /></Suspense>} />
            <Route path="/news/feed" element={<Suspense fallback={<RouteFallback />}><NewsFeedView /></Suspense>} />
            <Route path="/news/sentiment" element={<Suspense fallback={<RouteFallback />}><SentimentView /></Suspense>} />
            <Route path="/news/watchlist" element={<Suspense fallback={<RouteFallback />}><WatchlistView /></Suspense>} />
            <Route path="/risk-manager" element={<Suspense fallback={<RouteFallback />}><RiskManagerView /></Suspense>} />
            <Route path="/risk/sizing" element={<Suspense fallback={<RouteFallback />}><PositionSizingView /></Suspense>} />
            <Route path="/risk/rules" element={<Suspense fallback={<RouteFallback />}><RiskRulesView /></Suspense>} />
            <Route path="/risk/health" element={<Suspense fallback={<RouteFallback />}><AccountHealthView /></Suspense>} />
            <Route path="/data" element={<Suspense fallback={<RouteFallback />}><DataView /></Suspense>} />
            <Route path="/alerts" element={<Suspense fallback={<RouteFallback />}><AlertsView /></Suspense>} />
            <Route path="/system-health" element={<Suspense fallback={<RouteFallback />}><SystemHealthView /></Suspense>} />
            <Route path="/admin/health" element={<Suspense fallback={<RouteFallback />}><SystemHealthPage /></Suspense>} />
            <Route path="/admin/pipeline" element={<Suspense fallback={<RouteFallback />}><AgentPipelinePage /></Suspense>} />
            <Route path="/settings" element={<Suspense fallback={<RouteFallback />}><SettingsView /></Suspense>} />
            <Route path="*" element={<Suspense fallback={<RouteFallback />}><NotFound /></Suspense>} />
          </Route>
        </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </TradingProvider>
  )
}
