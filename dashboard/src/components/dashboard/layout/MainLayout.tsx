import React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { ErrorBoundary } from '../../ui/ErrorBoundary'

export function MainLayout() {
  const location = useLocation()
  return (
    <div className="flex h-screen overflow-hidden bg-space bg-grid relative text-primary font-sans">
      {/* Modern ambient glow decorators */}
      <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-0 left-20 w-[300px] h-[300px] bg-purple-500/5 rounded-full blur-[100px] pointer-events-none z-0" />
      
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        <TopBar />
        <main className="flex-1 overflow-auto custom-scrollbar">
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
