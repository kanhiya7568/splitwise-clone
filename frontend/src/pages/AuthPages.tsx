import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { DollarSign, ArrowRight } from 'lucide-react'
import { Button, Input, Card } from '../components/ui'
import { useLogin, useRegister } from '../hooks'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password required'),
})

export function LoginPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) })
  const login = useLogin()
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="size-10 bg-indigo-600 rounded-2xl flex items-center justify-center">
            <DollarSign className="size-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">Splitwise</span>
        </div>
        <Card className="p-6">
          <h1 className="text-2xl font-bold text-white mb-1">Welcome back</h1>
          <p className="text-zinc-400 text-sm mb-6">Sign in to your account</p>
          <form onSubmit={handleSubmit(d => login.mutate(d))} className="flex flex-col gap-4">
            <Input label="Email" type="email" placeholder="you@example.com" error={errors.email?.message} {...register('email')} />
            <Input label="Password" type="password" placeholder="••••••••" error={errors.password?.message} {...register('password')} />
            <Button type="submit" loading={login.isPending} className="w-full mt-2">
              Sign in <ArrowRight className="size-4" />
            </Button>
          </form>
        </Card>
        <p className="text-center text-zinc-500 text-sm mt-4">
          No account? <Link to="/register" className="text-indigo-400 hover:text-indigo-300">Create one</Link>
        </p>
      </div>
    </div>
  )
}

const registerSchema = z.object({
  first_name: z.string().min(1, 'First name required'),
  last_name: z.string().min(1, 'Last name required'),
  email: z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Min 8 characters'),
})

export function RegisterPage() {
  const { register, handleSubmit, formState: { errors } } = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema) })
  const reg = useRegister()
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="size-10 bg-indigo-600 rounded-2xl flex items-center justify-center">
            <DollarSign className="size-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">Splitwise</span>
        </div>
        <Card className="p-6">
          <h1 className="text-2xl font-bold text-white mb-1">Create account</h1>
          <p className="text-zinc-400 text-sm mb-6">Start splitting expenses with friends</p>
          <form onSubmit={handleSubmit(d => reg.mutate(d))} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Input label="First name" placeholder="Alex" error={errors.first_name?.message} {...register('first_name')} />
              <Input label="Last name" placeholder="Smith" error={errors.last_name?.message} {...register('last_name')} />
            </div>
            <Input label="Email" type="email" placeholder="you@example.com" error={errors.email?.message} {...register('email')} />
            <Input label="Password" type="password" placeholder="Min 8 characters" error={errors.password?.message} {...register('password')} />
            <Button type="submit" loading={reg.isPending} className="w-full mt-2">
              Create account <ArrowRight className="size-4" />
            </Button>
          </form>
        </Card>
        <p className="text-center text-zinc-500 text-sm mt-4">
          Already have an account? <Link to="/login" className="text-indigo-400 hover:text-indigo-300">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
