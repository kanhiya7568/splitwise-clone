import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'
import { Button } from '../components/ui'

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="text-center">
        <p className="text-8xl font-black text-white/10 mb-4">404</p>
        <h1 className="text-2xl font-bold text-white mb-2">Page not found</h1>
        <p className="text-zinc-400 mb-8">The page you're looking for doesn't exist.</p>
        <Link to="/"><Button><Home className="size-4" /> Go home</Button></Link>
      </div>
    </div>
  )
}
