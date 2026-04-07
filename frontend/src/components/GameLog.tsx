import { useEffect, useRef } from 'react'
import { EventMessage } from '../types'

interface Props {
  log: EventMessage[]
}

export default function GameLog({ log }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log.length])

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Game Log</h3>
      <div style={styles.scroll}>
        {log.map((entry, i) => (
          <LogEntry key={i} entry={entry} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function LogEntry({ entry }: { entry: EventMessage }) {
  const text = formatEvent(entry)
  if (!text) return null

  const isImportant =
    entry.event === 'PLAYER_ELIMINATED' ||
    entry.event === 'GAME_OVER' ||
    entry.event === 'CHALLENGE_WON' ||
    entry.event === 'BLOCK_CHALLENGE_WON'

  const isTurnStart = entry.event === 'TURN_START'

  return (
    <div
      style={{
        ...styles.entry,
        ...(isTurnStart ? styles.entryTurn : {}),
        ...(isImportant ? styles.entryImportant : {}),
      }}
    >
      {text}
    </div>
  )
}

function formatEvent(e: EventMessage): string | null {
  const ctx = e.ctx
  const p = e.player
  const state = e.state
  const turnNum = state ? state.turn_number + 1 : '?'

  switch (e.event) {
    case 'TURN_START':
      return `── Turn ${turnNum} — ${p?.name ?? '?'}'s turn ──`

    case 'ACTION_DECLARED': {
      if (!ctx) return null
      const target = ctx.target ? ` → ${ctx.target.name}` : ''
      const claim = ctx.claimed_character
        ? ` (claiming ${ctx.claimed_character_icon} ${ctx.claimed_character})`
        : ''
      return `▶ ${ctx.actor.name} declares ${ctx.action_icon} ${ctx.action}${claim}${target}`
    }

    case 'CHALLENGE_ISSUED':
      if (!ctx) return null
      return `⚔️ ${ctx.challenger?.name} challenges ${ctx.actor.name}'s claim of ${ctx.claimed_character_icon} ${ctx.claimed_character}`

    case 'CHALLENGE_WON':
      return `✅ Challenge succeeded! ${ctx?.actor.name ?? '?'} was bluffing.`

    case 'CHALLENGE_LOST':
      return `😬 Challenge failed! ${e.player_proved?.name ?? '?'} reveals ${e.proved_card?.icon} ${e.proved_card?.character}.`

    case 'BLOCK_DECLARED':
      if (!ctx) return null
      return `🛡️ ${ctx.blocker?.name} claims ${ctx.block_claimed_character_icon} ${ctx.block_claimed_character} to block ${ctx.actor.name}'s ${ctx.action_icon} ${ctx.action}`

    case 'BLOCK_CHALLENGE_ISSUED':
      if (!ctx) return null
      return `⚔️ ${ctx.actor.name} challenges ${ctx.blocker?.name}'s claim of ${ctx.block_claimed_character_icon} ${ctx.block_claimed_character}`

    case 'BLOCK_CHALLENGE_WON':
      return `✅ Block challenge succeeded! ${ctx?.blocker?.name ?? '?'} was bluffing.`

    case 'BLOCK_CHALLENGE_LOST':
      return `😬 Block challenge failed! ${e.player_proved?.name ?? '?'} reveals ${e.proved_card?.icon} ${e.proved_card?.character}.`

    case 'INFLUENCE_LOST':
      return `💀 ${p?.name} reveals ${e.card?.icon} ${e.card?.character} (${e.reason ?? ''})`

    case 'PLAYER_ELIMINATED':
      return `☠️ ${p?.name} has been eliminated!`

    case 'ACTION_EXECUTED': {
      if (!ctx) return null
      switch (ctx.action) {
        case 'Income':      return `💰 ${ctx.actor.name} takes 1 coin.`
        case 'Foreign Aid': return `🤲 ${ctx.actor.name} takes 2 coins.`
        case 'Tax':         return `💸 ${ctx.actor.name} collects tax (3 coins).`
        case 'Steal':       return `🦝 ${ctx.actor.name} steals from ${ctx.target?.name}.`
        case 'Coup':        return `💥 ${ctx.actor.name} stages a Coup against ${ctx.target?.name}.`
        case 'Assassinate': return `🗡️ ${ctx.actor.name} assassinates ${ctx.target?.name}.`
        case 'Exchange':    return `🔄 ${ctx.actor.name} completes an Ambassador exchange.`
        default:            return `✅ ${ctx.actor.name}: ${ctx.action}`
      }
    }

    case 'ACTION_BLOCKED':
      if (!ctx) return null
      return `🚫 ${ctx.action_icon} ${ctx.action} by ${ctx.actor.name} was blocked by ${ctx.blocker?.name}.`

    case 'ACTION_FAILED':
      if (!ctx) return null
      return `❌ ${ctx.actor.name}'s ${ctx.action_icon} ${ctx.action} failed (lost challenge).`

    case 'GAME_OVER':
      return `🏆 GAME OVER — ${e.winner?.name ?? '?'} wins!`

    default:
      return null
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
  },
  heading: {
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-muted)',
    marginBottom: '12px',
    flexShrink: 0,
  },
  scroll: {
    overflowY: 'auto',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    fontSize: '13px',
    lineHeight: '1.5',
    paddingRight: '4px',
  },
  entry: {
    padding: '4px 6px',
    borderRadius: '4px',
    color: 'var(--text)',
  },
  entryTurn: {
    color: 'var(--text-muted)',
    marginTop: '8px',
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  entryImportant: {
    color: '#fff',
    fontWeight: 600,
    background: 'rgba(255,255,255,0.05)',
  },
}
