import { NavLink } from 'react-router-dom'
import { Plane } from 'lucide-react'
import { ThemeToggle } from '@/components/theme-toggle'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Plane className="size-4" />
            </span>
            Northline
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                cn(buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'sm' }))
              }
            >
              Chat
            </NavLink>
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                cn(buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'sm' }))
              }
            >
              Admin
            </NavLink>
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <main className={cn('mx-auto max-w-7xl px-4 py-6 sm:px-6')}>{children}</main>
    </div>
  )
}
