export type CommandType = 'GOTO' | 'RETURN_HOME' | 'LAND'
export type CommandState =
  | 'PENDING' | 'SENT' | 'ACCEPTED' | 'COMPLETED' | 'REJECTED' | 'FAILED' | 'TIMED_OUT'

export interface TrackedCommand {
  command_id: string
  type: CommandType
  state: CommandState
  reason: string | null
}

const TERMINAL: ReadonlySet<CommandState> = new Set(['COMPLETED', 'REJECTED', 'FAILED', 'TIMED_OUT'])

export function isTerminal(state: CommandState): boolean {
  return TERMINAL.has(state)
}

/** Apply a poll answer only if it belongs to the command we're currently showing. */
export function applyPoll(
  current: TrackedCommand | null,
  fresh: TrackedCommand,
): TrackedCommand | null {
  if (current === null || current.command_id !== fresh.command_id) {
    return current
  }

  return fresh
}

async function errorMessage(res: Response): Promise<string> {
  const body = await res.json().catch(() => ({}))
  return typeof body.detail === 'string' ? body.detail : `request failed (${res.status})`
}

export async function sendCommand(body: object, idempotencyKey: string): Promise<TrackedCommand> {
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch('/api/v1/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await errorMessage(res))
      return res.json()
    } catch (e) {
      // fetch throws TypeError when the network fails: retry ONCE with the SAME key
      if (!(e instanceof TypeError) || attempt >= 2) throw e
    }
  }
}

export async function getCommand(commandId: string): Promise<TrackedCommand> {
  const res = await fetch(`/api/v1/commands/${commandId}`)
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}