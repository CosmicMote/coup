import { useState } from 'react'
import { DecisionMessage, DecisionOption, DecisionResponse } from '../types'

interface Props {
  decision: DecisionMessage
  onRespond: (response: DecisionResponse) => void
}

export default function DecisionPanel({ decision, onRespond }: Props) {
  function respond(value: string | string[]) {
    onRespond({
      type: 'decision_response',
      decision_id: decision.decision_id,
      value,
    })
  }

  return (
    <div style={styles.panel}>
      <PromptHeader decision={decision} />
      <PromptBody decision={decision} onRespond={respond} />
    </div>
  )
}

// ── Header describing what the player is deciding ─────────────────────

function PromptHeader({ decision }: { decision: DecisionMessage }) {
  const ctx = decision.ctx
  const prompt = decision.prompt

  let title = ''
  let subtitle = ''

  if (prompt === 'choose_action') {
    title = 'Choose your action'
    subtitle = "It's your turn."
  } else if (prompt === 'choose_target') {
    title = `Choose a target`
    subtitle = `${decision.action_icon ?? ''} ${decision.action ?? ''}`
  } else if (prompt === 'choose_block') {
    title = 'Block or pass?'
    subtitle = ctx
      ? `${ctx.actor.name} is attempting ${ctx.action_icon} ${ctx.action}.`
      : ''
  } else if (prompt === 'choose_challenge') {
    if (ctx?.blocker) {
      title = 'Challenge the block?'
      subtitle = `${ctx.blocker.name} claims ${ctx.block_claimed_character_icon ?? ''} ${ctx.block_claimed_character ?? ''} to block your ${ctx.action_icon} ${ctx.action}.`
    } else {
      title = 'Challenge or pass?'
      subtitle = ctx
        ? `${ctx.actor.name} claims ${ctx.claimed_character_icon ?? ''} ${ctx.claimed_character ?? ''} for ${ctx.action_icon} ${ctx.action}.`
        : ''
    }
  } else if (prompt === 'choose_card_to_lose') {
    title = '💀 Choose a card to lose'
    subtitle = decision.reason ?? 'You must lose an influence.'
  } else if (prompt === 'choose_exchange') {
    title = '🔄 Ambassador exchange'
    subtitle = `Choose ${decision.keep_count ?? '?'} card(s) to keep.`
  }

  return (
    <div style={styles.header}>
      <div style={styles.headerTitle}>{title}</div>
      {subtitle && <div style={styles.headerSubtitle}>{subtitle}</div>}
    </div>
  )
}

// ── Body: prompt-specific controls ────────────────────────────────────

function PromptBody({
  decision,
  onRespond,
}: {
  decision: DecisionMessage
  onRespond: (value: string | string[]) => void
}) {
  const { prompt, options } = decision

  if (prompt === 'choose_exchange') {
    return (
      <ExchangeChooser
        options={options}
        keepCount={decision.keep_count ?? 1}
        onRespond={onRespond}
      />
    )
  }

  // All other prompts: single-select button list
  return (
    <div style={styles.options}>
      {options.map(opt => (
        <OptionButton key={opt.id} option={opt} onSelect={() => onRespond(opt.id)} />
      ))}
    </div>
  )
}

function OptionButton({
  option,
  onSelect,
}: {
  option: DecisionOption
  onSelect: () => void
}) {
  return (
    <button style={styles.optionBtn} onClick={onSelect}>
      {option.icon && <span style={styles.optionIcon}>{option.icon}</span>}
      <span style={styles.optionLabel}>{option.label}</span>
      {option.coins !== undefined && (
        <span style={styles.optionMeta}>🪙 {option.coins}  {'❤️'.repeat(option.influence ?? 0)}</span>
      )}
    </button>
  )
}

function ExchangeChooser({
  options,
  keepCount,
  onRespond,
}: {
  options: DecisionOption[]
  keepCount: number
  onRespond: (value: string[]) => void
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set())

  function toggle(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < keepCount) {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div>
      <div style={styles.options}>
        {options.map(opt => (
          <button
            key={opt.id}
            style={{
              ...styles.optionBtn,
              ...(selected.has(opt.id) ? styles.optionBtnSelected : {}),
            }}
            onClick={() => toggle(opt.id)}
          >
            {opt.icon && <span style={styles.optionIcon}>{opt.icon}</span>}
            <span style={styles.optionLabel}>{opt.label}</span>
            {selected.has(opt.id) && <span style={styles.checkmark}>✓</span>}
          </button>
        ))}
      </div>
      <button
        style={{
          ...styles.confirmBtn,
          ...(selected.size !== keepCount ? styles.confirmBtnDisabled : {}),
        }}
        disabled={selected.size !== keepCount}
        onClick={() => onRespond(Array.from(selected))}
      >
        Keep {selected.size}/{keepCount} selected
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    background: 'var(--card-bg)',
    border: '2px solid var(--accent)',
    borderRadius: 'var(--radius)',
    padding: '20px',
    boxShadow: '0 0 20px rgba(233, 69, 96, 0.2)',
  },
  header: {
    marginBottom: '16px',
  },
  headerTitle: {
    fontSize: '17px',
    fontWeight: 700,
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    marginTop: '4px',
  },
  options: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  optionBtn: {
    background: 'rgba(255,255,255,0.06)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    padding: '10px 14px',
    textAlign: 'left',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    fontWeight: 500,
    borderRadius: 'var(--radius)',
    transition: 'background 0.15s, border-color 0.15s',
  },
  optionBtnSelected: {
    background: 'rgba(233, 69, 96, 0.18)',
    borderColor: 'var(--accent)',
    color: '#fff',
  },
  optionIcon: {
    fontSize: '1.2em',
    width: '24px',
    textAlign: 'center',
  },
  optionLabel: {
    flex: 1,
  },
  optionMeta: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  checkmark: {
    color: 'var(--accent)',
    fontWeight: 700,
  },
  confirmBtn: {
    marginTop: '12px',
    width: '100%',
    background: 'var(--accent)',
    color: '#fff',
    fontWeight: 600,
    padding: '10px',
  },
  confirmBtnDisabled: {
    background: 'var(--border)',
    color: 'var(--text-muted)',
  },
}
