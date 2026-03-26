import React, { useState, useEffect } from 'react'
import { TopBar } from './components/TopBar'
import { InTradeBar } from './components/InTradeBar'
import { BottomLogBar } from './components/BottomLogBar'
import { LoginPage } from './components/LoginPage'
import { DashboardSidebar, DashboardScreen } from './components/dashboard/DashboardSidebar'
import { PortfolioView } from './components/dashboard/Portfolio/PortfolioView'
import { OptionsView } from './components/dashboard/Options/OptionsView'
import { CryptoView } from './components/dashboard/Crypto/CryptoView'
import { BacktestView } from './components/dashboard/Backtest/BacktestView'
import { DataInventoryView } from './components/dashboard/Data/DataView'
import { AlertsView } from './components/dashboard/Alerts/AlertsView'
import { SettingsView } from './components/dashboard/Settings/SettingsView'
import { TradeView } from './components/dashboard/Trade/TradeView'
import { supabase, supabaseMisconfigured } from './lib/supabaseClient'
import type { Session } from '@supabase/supabase-js'
import { TradingProvider } from './context/TradingContext'


export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    if (supabaseMisconfigured) {
      setAuthError('Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in Netlify environment variables, then redeploy.')
      setAuthLoading(false)
      return
    }

    supabase.auth.getSession().then(({ data: { session }, error }) => {
      if (error) {
        setAuthError(`Auth error: ${error.message}`)
      }
      setSession(session)
      setAuthLoading(false)
    }).catch((err) => {
      setAuthError(`Connection failed: ${err.message}`)
      setAuthLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
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
      <DashboardLayout />
    </TradingProvider>
  )
}

function DashboardLayout() {
  const [activeScreen, setActiveScreen] = useState<DashboardScreen>('trade')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* TOP BAR */}
      <TopBar />

      {/* IN TRADE BAR */}
      <InTradeBar />

      {/* MAIN CONTENT AREA */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        
        {/* DASHBOARD SIDEBAR */}
        <DashboardSidebar 
          activeScreen={activeScreen} 
          onScreenChange={setActiveScreen}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* SCREEN CONTENT */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', background: 'var(--bg-primary)' }}>
          {activeScreen === 'portfolio' && <PortfolioView />}
          {activeScreen === 'options' && <OptionsView />}
          {activeScreen === 'crypto' && <CryptoView />}
          {activeScreen === 'backtest' && <BacktestView symbol="IWM" timeframe="15m" />}
          {activeScreen === 'data' && <DataInventoryView />}
          {activeScreen === 'alerts' && <AlertsView />}
          {activeScreen === 'settings' && <SettingsView />}
          {activeScreen === 'trade' && <TradeView />}
        </div>
      </div>

      {/* BOTTOM LOG BAR */}
      <BottomLogBar />
    </div>
  )
}
