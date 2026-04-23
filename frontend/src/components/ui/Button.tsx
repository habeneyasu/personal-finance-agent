import React from 'react'
import { cn } from '../lib/utils'
import { Loader2 } from 'lucide-react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
  children: React.ReactNode
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading = false, icon, children, disabled, ...props }, ref) => {
    const baseClasses = 'inline-flex items-center justify-center font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-secondary-900 disabled:opacity-50 disabled:cursor-not-allowed'
    
    const variants = {
      primary: 'bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500 shadow-soft',
      secondary: 'bg-secondary-800 text-secondary-100 border border-secondary-700 hover:bg-secondary-700 focus:ring-secondary-500',
      ghost: 'text-secondary-300 hover:bg-secondary-800 hover:text-secondary-100 focus:ring-secondary-500',
      danger: 'bg-error-600 text-white hover:bg-error-700 focus:ring-error-500 shadow-soft',
      success: 'bg-success-600 text-white hover:bg-success-700 focus:ring-success-500 shadow-soft',
    }
    
    const sizes = {
      sm: 'rounded-md px-3 py-1.5 text-xs',
      md: 'rounded-lg px-4 py-2 text-sm',
      lg: 'rounded-xl px-6 py-3 text-base',
    }
    
    const classes = cn(
      baseClasses,
      variants[variant],
      sizes[size],
      className
    )
    
    return (
      <button
        className={classes}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        )}
        {!loading && icon && (
          <span className="mr-2">{icon}</span>
        )}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'

export default Button
