import { SerializedPlayer } from '../types'

interface Props {
  players: SerializedPlayer[]
  currentPlayerId: number
  humanPlayerId: number
}

export default function PlayerBoard({ players, currentPlayerId, humanPlayerId }: Props) {
  return (
    <div style={styles.board}>
      <h3 style={styles.heading}>Players</h3>
      {players.map(p => (
        <PlayerRow
          key={p.player_id}
          player={p}
          isCurrent={p.player_id === currentPlayerId}
          isHuman={p.player_id === humanPlayerId}
        />
      ))}
    </div>
  )
}

function PlayerRow({
  player,
  isCurrent,
  isHuman,
}: {
  player: SerializedPlayer
  isCurrent: boolean
  isHuman: boolean
}) {
  const eliminated = !player.is_alive

  return (
    <div
      style={{
        ...styles.row,
        ...(isCurrent && !eliminated ? styles.rowActive : {}),
        ...(eliminated ? styles.rowEliminated : {}),
      }}
    >
      <div style={styles.nameRow}>
        <span style={styles.name}>
          {isCurrent && !eliminated && <span style={styles.turnIndicator}>▶ </span>}
          {player.name}
          {isHuman && <span style={styles.youBadge}> (you)</span>}
        </span>
        {eliminated && <span style={styles.eliminated}>☠️ eliminated</span>}
      </div>

      {!eliminated && (
        <div style={styles.stats}>
          <span style={styles.coins}>
            🪙 {player.coins}
          </span>
          <span style={styles.influence}>
            {'❤️'.repeat(player.influence_count)}
          </span>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  board: {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  heading: {
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
    marginBottom: '4px',
  },
  row: {
    padding: '10px 12px',
    borderRadius: 'var(--radius)',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid transparent',
    transition: 'all 0.2s',
  },
  rowActive: {
    border: '1px solid var(--accent)',
    background: 'rgba(233, 69, 96, 0.08)',
  },
  rowEliminated: {
    opacity: 0.4,
  },
  nameRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  name: {
    fontWeight: 600,
    fontSize: '15px',
  },
  turnIndicator: {
    color: 'var(--accent)',
  },
  youBadge: {
    color: 'var(--text-muted)',
    fontWeight: 400,
    fontSize: '12px',
  },
  eliminated: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  stats: {
    display: 'flex',
    gap: '16px',
    marginTop: '4px',
    fontSize: '14px',
  },
  coins: {
    color: 'var(--gold)',
  },
  influence: {
    letterSpacing: '2px',
  },
}
