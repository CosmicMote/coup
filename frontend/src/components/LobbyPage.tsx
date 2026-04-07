import { useState, FormEvent } from 'react'

interface Props {
  onGameCreated: (gameId: string, humanName: string) => void
}

export default function LobbyPage({ onGameCreated }: Props) {
  const [humanName, setHumanName] = useState('You')
  const [numPlayers, setNumPlayers] = useState(4)
  const [aiType, setAiType] = useState<'basic' | 'adaptive'>('basic')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/games', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          num_players: numPlayers,
          human_name: humanName.trim() || 'You',
          cpu_ai_type: aiType,
        }),
      })

      if (!res.ok) {
        const data = await res.json() as { detail?: string }
        throw new Error(data.detail ?? 'Failed to create game')
      }

      const data = await res.json() as { game_id: string }
      onGameCreated(data.game_id, humanName.trim() || 'You')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.outer}>
      <div style={styles.card}>
        <h1 style={styles.title}>🎮 Coup</h1>
        <p style={styles.subtitle}>The game of deception and deduction</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label htmlFor="name">Your name</label>
            <input
              id="name"
              type="text"
              value={humanName}
              onChange={e => setHumanName(e.target.value)}
              maxLength={30}
              autoFocus
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="players">Number of players</label>
            <select
              id="players"
              value={numPlayers}
              onChange={e => setNumPlayers(Number(e.target.value))}
            >
              {[2, 3, 4, 5, 6].map(n => (
                <option key={n} value={n}>{n} players (you + {n - 1} CPU)</option>
              ))}
            </select>
          </div>

          <div style={styles.field}>
            <label htmlFor="ai">CPU AI strategy</label>
            <select
              id="ai"
              value={aiType}
              onChange={e => setAiType(e.target.value as 'basic' | 'adaptive')}
            >
              <option value="basic">Basic — personality-driven random play</option>
              <option value="adaptive">Adaptive — opponent modelling + threat scoring</option>
            </select>
          </div>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" style={styles.startBtn} disabled={loading}>
            {loading ? 'Starting…' : '▶ Start Game'}
          </button>
        </form>

        <div style={styles.rulesHint}>
          <p>Be the last player with influence. Bluff freely — or get caught trying.</p>
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  outer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    padding: '24px',
  },
  card: {
    background: 'var(--panel)',
    borderRadius: '12px',
    border: '1px solid var(--border)',
    padding: '40px 48px',
    width: '100%',
    maxWidth: '460px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
  },
  title: {
    fontSize: '2.2rem',
    textAlign: 'center',
    marginBottom: '4px',
  },
  subtitle: {
    textAlign: 'center',
    color: 'var(--text-muted)',
    marginBottom: '32px',
    fontSize: '14px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  error: {
    color: 'var(--red)',
    fontSize: '13px',
    padding: '8px 12px',
    background: 'rgba(233, 69, 96, 0.1)',
    borderRadius: 'var(--radius)',
    border: '1px solid rgba(233, 69, 96, 0.3)',
  },
  startBtn: {
    background: 'var(--accent)',
    color: '#fff',
    fontWeight: 600,
    fontSize: '16px',
    padding: '12px',
    marginTop: '4px',
  },
  rulesHint: {
    marginTop: '28px',
    padding: '16px',
    background: 'rgba(255,255,255,0.04)',
    borderRadius: 'var(--radius)',
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
}
