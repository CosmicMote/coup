import { useEffect, useRef, useCallback, useState } from 'react'
import {
  ServerMessage,
  DecisionMessage,
  EventMessage,
  SerializedState,
  DecisionResponse,
} from '../types'

export interface GameWebSocketState {
  connected: boolean
  gameState: SerializedState | null
  log: EventMessage[]
  pendingDecision: DecisionMessage | null
  winner: { player_id: number; name: string } | null
  error: string | null
}

export function useGameWebSocket(gameId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [state, setState] = useState<GameWebSocketState>({
    connected: false,
    gameState: null,
    log: [],
    pendingDecision: null,
    winner: null,
    error: null,
  })

  useEffect(() => {
    if (!gameId) return

    // In development the Vite proxy rewrites this to ws://localhost:8080/ws/...
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/${gameId}`

    let active = true   // set to false on cleanup so stale callbacks are ignored
    let retries = 0
    const MAX_RETRIES = 3

    function connect() {
      if (!active) return
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!active) {
          // This socket was opened by a React StrictMode mount that has
          // already been cleaned up.  Close it without sending "ready" so
          // the server never starts the engine on this dead connection.
          ws.close()
          return
        }
        retries = 0
        // Tell the server the connection is stable so it can start the engine.
        ws.send(JSON.stringify({ type: 'ready' }))
        setState(s => ({ ...s, connected: true, error: null }))
      }

      ws.onmessage = (event: MessageEvent) => {
        if (!active) return
        const msg: ServerMessage = JSON.parse(event.data as string)

        setState(s => {
          if (msg.type === 'event') {
            const newLog = [...s.log, msg]
            const newState = msg.state ?? s.gameState
            const winner =
              msg.event === 'GAME_OVER' && msg.winner ? msg.winner : s.winner
            return { ...s, log: newLog, gameState: newState, winner }
          }

          if (msg.type === 'decision') {
            return { ...s, pendingDecision: msg, gameState: msg.state }
          }

          if (msg.type === 'error') {
            return { ...s, error: msg.message }
          }

          return s
        })
      }

      ws.onclose = () => {
        if (!active) return
        setState(s => ({ ...s, connected: false }))
      }

      ws.onerror = () => {
        if (!active) return
        // Retry a few times before giving up — handles React StrictMode's
        // double-effect where the first connection is briefly closed and
        // re-opened within the same render cycle.
        if (retries < MAX_RETRIES) {
          retries++
          retryTimerRef.current = setTimeout(connect, 300 * retries)
        } else {
          setState(s => ({ ...s, error: 'WebSocket connection error' }))
        }
      }
    }

    connect()

    return () => {
      active = false
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
    }
  }, [gameId])

  const sendDecision = useCallback((response: DecisionResponse) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(response))
      setState(s => ({ ...s, pendingDecision: null }))
    }
  }, [])

  return { ...state, sendDecision }
}
