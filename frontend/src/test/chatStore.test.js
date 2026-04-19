import { describe, it, expect, beforeEach } from 'vitest'
import { act } from 'react'
import useChatStore from '../stores/chatStore'

describe('chatStore', () => {
    beforeEach(() => {
        useChatStore.setState({
            messages: [],
            streaming: false,
            streamingContent: '',
            pendingConfirm: false,
            sessionId: null,
            error: null,
        })
    })

    it('addUserMessage appends to messages', () => {
        act(() => {
            useChatStore.getState().addUserMessage('Hello')
        })
        expect(useChatStore.getState().messages).toHaveLength(1)
        expect(useChatStore.getState().messages[0]).toEqual({ role: 'user', content: 'Hello' })
    })

    it('startStreaming sets streaming=true and clears content', () => {
        act(() => {
            useChatStore.getState().startStreaming()
        })
        const state = useChatStore.getState()
        expect(state.streaming).toBe(true)
        expect(state.streamingContent).toBe('')
    })

    it('appendToken accumulates tokens', () => {
        act(() => {
            useChatStore.getState().startStreaming()
            useChatStore.getState().appendToken('Hello')
            useChatStore.getState().appendToken(' world')
        })
        expect(useChatStore.getState().streamingContent).toBe('Hello world')
    })

    it('finishStreaming moves streamingContent to messages', () => {
        act(() => {
            useChatStore.getState().addUserMessage('Hi')
            useChatStore.getState().startStreaming()
            useChatStore.getState().appendToken('Response text')
            useChatStore.getState().finishStreaming(false)
        })
        const state = useChatStore.getState()
        expect(state.streaming).toBe(false)
        expect(state.streamingContent).toBe('')
        expect(state.messages).toHaveLength(2)
        expect(state.messages[1]).toEqual({ role: 'assistant', content: 'Response text' })
    })

    it('finishStreaming sets pendingConfirm when flag is true', () => {
        act(() => {
            useChatStore.getState().startStreaming()
            useChatStore.getState().appendToken('confirm needed')
            useChatStore.getState().finishStreaming(true)
        })
        expect(useChatStore.getState().pendingConfirm).toBe(true)
    })

    it('clearPendingConfirm resets flag', () => {
        act(() => {
            useChatStore.setState({ pendingConfirm: true })
            useChatStore.getState().clearPendingConfirm()
        })
        expect(useChatStore.getState().pendingConfirm).toBe(false)
    })
})
