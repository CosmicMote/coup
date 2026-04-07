import { useGameWebSocket } from '../hooks/useGameWebSocket'
import PlayerBoard from './PlayerBoard'
import MyHand from './MyHand'
import DecisionPanel from './DecisionPanel'
import GameLog from './GameLog'

interface Props {
  gameId: string
  humanName: string
  onPlayAgain: () => void
}

// The human player is always player_id=0 (first in the list, as created by the server).
const HUMAN_PLAYER_ID = 0

export default function GamePage({ gameId, humanName, onPlayAgain }: Props) {
  const { connected, gameState, log, pendingDecision, winner, error, sendDecision } =
    useGameWebSocket(gameId)

  // ── Loading / error states ──────────────────────────────────────────
  if (error) {
    return (
      <div style={styles.centered}>
        <div style={styles.errorBox}>
          <h2>Something went wrong</h2>
          <p style={{ color: 'var(--text-muted)', margin: '12px 0' }}>{error}</p>
          <button style={styles.accentBtn} onClick={onPlayAgain}>Back to lobby</button>
        </div>
      </div>
    )
  }

  if (!connected || !gameState) {
    return (
      <div style={styles.centered}>
        <div style={styles.spinner}>Connecting…</div>
      </div>
    )
  }

  const humanPlayer = gameState.players.find(p => p.player_id === HUMAN_PLAYER_ID)

  return (
    <div style={styles.layout}>
      {/* Left: player list */}
      <aside style={styles.sidebar}>
        <PlayerBoard
          players={gameState.players}
          currentPlayerId={gameState.current_player_id}
          humanPlayerId={HUMAN_PLAYER_ID}
        />

        <div style={styles.deckInfo}>
          🃏 {gameState.deck_size} cards in deck
        </div>
      </aside>

      {/* Center: hand + decision */}
      <main style={styles.main}>
        {humanPlayer && (
          <MyHand
            cards={humanPlayer.hand}
            playerName={humanName}
          />
        )}

        {pendingDecision ? (
          <DecisionPanel decision={pendingDecision} onRespond={sendDecision} />
        ) : winner ? (
          <WinnerBanner winner={winner} humanName={humanName} onPlayAgain={onPlayAgain} />
        ) : (
          <WaitingBanner gameState={gameState} humanPlayerId={HUMAN_PLAYER_ID} />
        )}
      </main>

      {/* Right: game log */}
      <aside style={styles.logPanel}>
        <GameLog log={log} />
      </aside>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────

function WaitingBanner({
  gameState,
  humanPlayerId,
}: {
  gameState: { current_player_id: number; players: Array<{ player_id: number; name: string }> }
  humanPlayerId: number
}) {
  const current = gameState.players.find(
    p => p.player_id === gameState.current_player_id,
  )
  const isYourTurn = gameState.current_player_id === humanPlayerId

  return (
    <div style={styles.waitingBanner}>
      {isYourTurn ? (
        <span>It's your turn — choose an action above.</span>
      ) : (
        <span>Waiting for <strong>{current?.name ?? '?'}</strong>…</span>
      )}
    </div>
  )
}

function WinnerBanner({
  winner,
  humanName,
  onPlayAgain,
}: {
  winner: { player_id: number; name: string }
  humanName: string
  onPlayAgain: () => void
}) {
  const youWon = winner.name === humanName

  return (
    <div style={styles.winnerBanner}>
      <div style={styles.winnerEmoji}>{youWon ? '🏆' : '😔'}</div>
      <div style={styles.winnerTitle}>
        {youWon ? 'You win!' : `${winner.name} wins!`}
      </div>
      <div style={styles.winnerSubtitle}>
        {youWon ? 'Outstanding deception.' : 'Better luck next time.'}
      </div>
      <button style={styles.accentBtn} onClick={onPlayAgain}>
        Play again
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  layout: {
    display: 'grid',
    gridTemplateColumns: '220px 1fr 280px',
    gridTemplateRows: '100vh',
    gap: '0',
    height: '100vh',
    overflow: 'hidden',
  },
  sidebar: {
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    borderRight: '1px solid var(--border)',
    overflowY: 'auto',
  },
  main: {
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    overflowY: 'auto',
  },
  logPanel: {
    borderLeft: '1px solid var(--border)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    padding: '16px',
  },
  deckInfo: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    textAlign: 'center',
    padding: '8px',
  },
  waitingBanner: {
    padding: '16px 20px',
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    color: 'var(--text-muted)',
    fontSize: '14px',
  },
  winnerBanner: {
    padding: '32px',
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    textAlign: 'center',
  },
  winnerEmoji: {
    fontSize: '3rem',
  },
  winnerTitle: {
    fontSize: '1.8rem',
    fontWeight: 700,
  },
  winnerSubtitle: {
    color: 'var(--text-muted)',
    fontSize: '14px',
  },
  accentBtn: {
    background: 'var(--accent)',
    color: '#fff',
    fontWeight: 600,
    padding: '10px 24px',
    fontSize: '15px',
    marginTop: '4px',
  },
  centered: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
  },
  spinner: {
    color: 'var(--text-muted)',
    fontSize: '1.1rem',
  },
  errorBox: {
    background: 'var(--panel)',
    border: '1px solid var(--red)',
    borderRadius: 'var(--radius)',
    padding: '32px 40px',
    maxWidth: '420px',
    textAlign: 'center',
  },
}
