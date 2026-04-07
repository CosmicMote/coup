import { useState } from 'react'
import LobbyPage from './components/LobbyPage'
import GamePage from './components/GamePage'

interface GameInfo {
  gameId: string
  humanName: string
}

export default function App() {
  const [game, setGame] = useState<GameInfo | null>(null)

  function handleGameCreated(gameId: string, humanName: string) {
    setGame({ gameId, humanName })
  }

  function handlePlayAgain() {
    setGame(null)
  }

  if (!game) {
    return <LobbyPage onGameCreated={handleGameCreated} />
  }

  return (
    <GamePage
      gameId={game.gameId}
      humanName={game.humanName}
      onPlayAgain={handlePlayAgain}
    />
  )
}
