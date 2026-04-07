// ── Card / Player / State ──────────────────────────────────────────────

export interface SerializedCard {
  character: string | null   // null = opponent's hidden card
  character_icon: string | null
  revealed: boolean
}

export interface SerializedPlayer {
  player_id: number
  name: string
  coins: number
  is_alive: boolean
  influence_count: number
  is_human: boolean
  hand: SerializedCard[]
}

export interface SerializedState {
  turn_number: number
  current_player_id: number
  players: SerializedPlayer[]
  deck_size: number
}

// ── Action context ─────────────────────────────────────────────────────

export interface SerializedCtx {
  actor: { player_id: number; name: string }
  action: string
  action_icon: string
  target: { player_id: number; name: string } | null
  claimed_character: string | null
  claimed_character_icon: string | null
  challenger: { player_id: number; name: string } | null
  blocker: { player_id: number; name: string } | null
  block_claimed_character: string | null
  block_claimed_character_icon: string | null
}

// ── Decision messages (server → client) ───────────────────────────────

export type PromptType =
  | 'choose_action'
  | 'choose_target'
  | 'choose_block'
  | 'choose_challenge'
  | 'choose_card_to_lose'
  | 'choose_exchange'

export interface DecisionOption {
  id: string
  label: string
  icon?: string
  coins?: number
  influence?: number
}

export interface DecisionMessage {
  type: 'decision'
  decision_id: string
  prompt: PromptType
  state: SerializedState
  options: DecisionOption[]
  ctx?: SerializedCtx
  action?: string
  action_icon?: string
  reason?: string
  keep_count?: number
}

// ── Event messages (server → client) ──────────────────────────────────

export type EventName =
  | 'TURN_START'
  | 'ACTION_DECLARED'
  | 'CHALLENGE_ISSUED'
  | 'CHALLENGE_WON'
  | 'CHALLENGE_LOST'
  | 'BLOCK_DECLARED'
  | 'BLOCK_CHALLENGE_ISSUED'
  | 'BLOCK_CHALLENGE_WON'
  | 'BLOCK_CHALLENGE_LOST'
  | 'INFLUENCE_LOST'
  | 'PLAYER_ELIMINATED'
  | 'ACTION_EXECUTED'
  | 'ACTION_BLOCKED'
  | 'ACTION_FAILED'
  | 'GAME_OVER'

export interface EventMessage {
  type: 'event'
  event: EventName
  state: SerializedState | null
  ctx?: SerializedCtx
  player?: { player_id: number; name: string }
  winner?: { player_id: number; name: string }
  card?: { character: string; icon: string }
  reason?: string
  player_proved?: { player_id: number; name: string }
  proved_card?: { character: string; icon: string }
}

export interface ErrorMessage {
  type: 'error'
  code: string
  message: string
}

export type ServerMessage = DecisionMessage | EventMessage | ErrorMessage

// ── Client → server ────────────────────────────────────────────────────

export interface DecisionResponse {
  type: 'decision_response'
  decision_id: string
  value: string | string[]
}
