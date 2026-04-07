import { SerializedCard } from '../types'

interface Props {
  cards: SerializedCard[]
  playerName: string
}

export default function MyHand({ cards, playerName }: Props) {
  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>🃏 {playerName}'s hand</h3>
      <div style={styles.cards}>
        {cards.map((card, i) => (
          <CardTile key={i} card={card} />
        ))}
      </div>
    </div>
  )
}

function CardTile({ card }: { card: SerializedCard }) {
  const revealed = card.revealed

  return (
    <div style={{ ...styles.card, ...(revealed ? styles.cardRevealed : {}) }}>
      {revealed ? (
        <>
          <span style={styles.icon}>{card.character_icon ?? '❓'}</span>
          <span style={styles.charName}>{card.character ?? 'Unknown'}</span>
          <span style={styles.revealedLabel}>revealed</span>
        </>
      ) : card.character ? (
        <>
          <span style={styles.icon}>{card.character_icon}</span>
          <span style={styles.charName}>{card.character}</span>
        </>
      ) : (
        <>
          <span style={styles.icon}>❓</span>
          <span style={styles.charName}>Hidden</span>
        </>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '16px',
  },
  heading: {
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
    marginBottom: '12px',
  },
  cards: {
    display: 'flex',
    gap: '12px',
  },
  card: {
    background: 'var(--card-bg)',
    border: '2px solid var(--border)',
    borderRadius: '10px',
    padding: '16px 20px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
    minWidth: '100px',
    flex: 1,
  },
  cardRevealed: {
    opacity: 0.5,
    border: '2px solid var(--red)',
  },
  icon: {
    fontSize: '2rem',
  },
  charName: {
    fontWeight: 600,
    fontSize: '14px',
  },
  revealedLabel: {
    fontSize: '11px',
    color: 'var(--red)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
}
