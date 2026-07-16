import React from 'react'
import { Link } from 'react-router-dom'
import { LayoutDashboard, AlertCircle } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-6 p-8 text-center">
      <AlertCircle className="w-12 h-12 text-muted-foreground opacity-40" />
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">404 — Page Not Found</h1>
        <p className="text-sm text-muted-foreground max-w-sm">
          This page doesn't exist. It may have been moved or the URL is incorrect.
        </p>
      </div>
      <Link
        to="/"
        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 text-sm font-semibold transition-colors"
      >
        <LayoutDashboard size={16} />
        Back to Control Tower
      </Link>
    </div>
  )
}
