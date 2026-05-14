import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './components/LoginPage'
import { MainLayout } from './components/dashboard/layout/MainLayout'
import OverviewView from './components/dashboard/Overview/OverviewView'
import EquitiesTradeView from './components/dashboard/Equities/EquitiesTradeView'
import EquitiesMonitorView from './components/dashboard/Equities/EquitiesMonitorView'
import EquitiesPerformanceView from './components/dashboard/Equities/EquitiesPerformanceView'
import EquitiesStrategyView from './components/dashboard/Equities/EquitiesStrategyView'
import CryptoTradeView from './components/dashboard/Crypto/CryptoTradeView'
import CryptoMonitorView from './components/dashboard/Crypto/CryptoMonitorView'
import CryptoPerformanceView from './components/dashboard/Crypto/CryptoPerformanceView'
import CryptoStrategyView from './components/dashboard/Crypto/CryptoStrategyView'
import StrategyLabView from './components/dashboard/StrategyLab/StrategyLabView'
import NewsFeedView from './components/dashboard/NewsSocial/NewsFeedView'
import SentimentView from './components/dashboard/NewsSocial/SentimentView'
import WatchlistView from './components/dashboard/NewsSocial/WatchlistView'
import PositionSizingView from './components/dashboard/RiskManager/PositionSizingView'
import RiskRulesView from './components/dashboard/RiskManager/RiskRulesView'
import AccountHealthView from './components/dashboard/RiskManager/AccountHealthView'
import RiskManagerView from './components/dashboard/RiskManager/RiskManagerView'
import { DataView } from './components/dashboard/Data/DataView'
import { AlertsView } from './components/dashboard/Alerts/AlertsView'
import SystemHealthView from './components/dashboard/SystemHealth/SystemHealthView'
import { SettingsView } from './components/dashboard/Settings/SettingsView'
import { supabase, supabaseMisconfigured } from './lib/supabaseClient'
import { toUserMessage } from './lib/apiError'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import type { Session } from '@supabase/supabase-js'
import { TradingProvider } from './context/TradingContext'

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
      setSession(s)
      setAuthLoading(false)
    }).catch((err) => {
      setAuthError(toUserMessage(err))
      setAuthLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s)
    })

    return () => subscription.unsubscribe()
  }, [])

  if (authLoading) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-primary)', color: 'var(--text-muted)'
      }}>
        Initializing...
      </div>
    )
  }

  if (authError) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: '1rem',
        background: 'var(--bg-primary)', color: 'var(--text-muted)', padding: '2rem'
      }}>
        <div style={{ color: '#ef4444', fontWeight: 600, fontSize: '1.2rem' }}>Configuration Error</div>
        <div style={{ maxWidth: '500px', textAlign: 'center', lineHeight: 1.6 }}>{authError}</div>
      </div>
    )
  }

  if (!session) {
    return <LoginPage />
  }

  return (
    <TradingProvider>
      <BrowserRouter>
        <ErrorBoundary>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<OverviewView />} />
            <Route path="/equities/trade" element={<EquitiesTradeView />} />
            <Route path="/equities/monitor" element={<EquitiesMonitorView />} />
            <Route path="/equities/performance" element={<EquitiesPerformanceView />} />
            <Route path="/equities/strategy" element={<EquitiesStrategyView />} />
            <Route path="/crypto/trade" element={<CryptoTradeView />} />
            <Route path="/crypto/monitor" element={<CryptoMonitorView />} />
            <Route path="/crypto/performance" element={<CryptoPerformanceView />} />
            <Route path="/crypto/strategy" element={<CryptoStrategyView />} />
            <Route path="/strategy-lab" element={<StrategyLabView />} />
            <Route path="/strategy-lab/editor" element={<StrategyLabView />} />
            <Route path="/strategy-lab/backtest" element={<StrategyLabView />} />
            <Route path="/news/feed" element={<NewsFeedView />} />
            <Route path="/news/sentiment" element={<SentimentView />} />
            <Route path="/news/watchlist" element={<WatchlistView />} />
            <Route path="/risk-manager" element={<RiskManagerView />} />
            <Route path="/risk/sizing" element={<PositionSizingView />} />
            <Route path="/risk/rules" element={<RiskRulesView />} />
            <Route path="/risk/health" element={<AccountHealthView />} />
            <Route path="/data" element={<DataView />} />
            <Route path="/alerts" element={<AlertsView />} />
            <Route path="/system-health" element={<SystemHealthView />} />
            <Route path="/settings" element={<SettingsView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </TradingProvider>
  )
}
