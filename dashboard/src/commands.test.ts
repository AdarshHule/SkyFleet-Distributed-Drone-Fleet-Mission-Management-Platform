import { describe, expect, it } from 'vitest'
import { applyPoll, isTerminal, type TrackedCommand } from './commands'

const cmd = (command_id: string, state: TrackedCommand['state']): TrackedCommand =>
  ({ command_id, type: 'LAND', state, reason: null })

describe('isTerminal', () => {
  it('knows which states are final', () => {
    expect(isTerminal('ACCEPTED')).toBe(false)
    expect(isTerminal('TIMED_OUT')).toBe(true)
  })
})

describe('applyPoll', () => {
  it('updates the command being shown', () => {
    const fresh = cmd('a', 'ACCEPTED')
    expect(applyPoll(cmd('a', 'SENT'), fresh)).toBe(fresh)
  })

  it('ignores a late answer about an older command', () => {
    const shown = cmd('b', 'PENDING')
    expect(applyPoll(shown, cmd('a', 'COMPLETED'))).toBe(shown)
  })

  it('ignores answers when nothing is shown', () => {
    expect(applyPoll(null, cmd('a', 'SENT'))).toBeNull()
  })
})