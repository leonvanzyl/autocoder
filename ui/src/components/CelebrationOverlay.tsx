import { useCallback, useEffect, useState } from 'react'
import { Sparkles, PartyPopper } from 'lucide-react'
import { AgentAvatar } from './AgentAvatar'
import type { AgentMascot } from '../lib/types'

interface CelebrationOverlayProps {
  agentName: AgentMascot | 'Unknown'
  featureName: string
  onComplete?: () => void
}

// Generate random confetti particles
function generateConfetti(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    delay: Math.random() * 0.5,
    duration: 1 + Math.random() * 1,
    color: ['#ff006e', '#ffd60a', '#70e000', '#00b4d8', '#8338ec'][Math.floor(Math.random() * 5)],
    rotation: Math.random() * 360,
  }))
}

export function CelebrationOverlay({ agentName, featureName, onComplete }: CelebrationOverlayProps) {
  const [isVisible, setIsVisible] = useState(true)
  const [confetti] = useState(() => generateConfetti(30))

  const dismiss = useCallback(() => {
    setIsVisible(false)
    setTimeout(() => onComplete?.(), 300) // Wait for fade animation
  }, [onComplete])

  useEffect(() => {
    // Auto-dismiss after 3 seconds
    const timer = setTimeout(dismiss, 3000)

    // Escape key to dismiss early
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        dismiss()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [dismiss])

  if (!isVisible) {
    return null
  }

  return (
    <div
      className={`
        fixed inset-0 z-50 flex items-center justify-center
        pointer-events-none
        transition-opacity duration-300
        ${isVisible ? 'opacity-100' : 'opacity-0'}
      `}
    >
      {/* Confetti particles */}
      <div className="absolute inset-0 overflow-hidden">
        {confetti.map((particle) => (
          <div
            key={particle.id}
            className="absolute w-3 h-3 animate-confetti"
            style={{
              left: `${particle.x}%`,
              top: '-20px',
              backgroundColor: particle.color,
              animationDelay: `${particle.delay}s`,
              animationDuration: `${particle.duration}s`,
              transform: `rotate(${particle.rotation}deg)`,
            }}
          />
        ))}
      </div>

      {/* Celebration card - click to dismiss */}
      <button
        type="button"
        onClick={dismiss}
        className="neo-card p-6 bg-[var(--color-neo-done)] animate-bounce-in pointer-events-auto cursor-pointer hover:scale-105 transition-transform focus:outline-none focus:ring-2 focus:ring-neo-accent"
      >
        <div className="flex flex-col items-center gap-4">
          {/* Icons */}
          <div className="flex items-center gap-2">
            <Sparkles size={24} className="text-neo-pending animate-pulse" />
            <PartyPopper size={28} className="text-neo-accent" />
            <Sparkles size={24} className="text-neo-pending animate-pulse" />
          </div>

          {/* Avatar celebrating */}
          <AgentAvatar name={agentName} state="success" size="lg" />

          {/* Message */}
          <div className="text-center">
            <h3 className="font-display text-lg font-bold text-neo-text-on-bright mb-1">
              Feature Complete!
            </h3>
            <p className="text-sm text-neo-text-on-bright/80 max-w-[200px] truncate">
              {featureName}
            </p>
            <p className="text-xs text-neo-text-on-bright/60 mt-2">
              Great job, {agentName}!
            </p>
          </div>

          {/* Dismiss hint */}
          <p className="text-xs text-neo-text-on-bright/40 mt-1">
            Click or press Esc to dismiss
          </p>
        </div>
      </button>
    </div>
  )
}
