import { create } from 'zustand'

/**
 * chatStore — conversation history + SSE streaming state
 */
const useChatStore = create((set, get) => ({
    messages: [],          // [{ role: 'user'|'assistant', content: string, toolCalls?: [] }]
    streaming: false,      // true while SSE is open
    streamingContent: '',  // partial assistant message being built
    pendingConfirm: false, // true when agent returns confirmation-required warning
    sessionId: null,
    error: null,

    setSessionId: (sessionId) => set({ sessionId }),

    addUserMessage: (content) =>
        set((state) => ({
            messages: [...state.messages, { role: 'user', content }],
        })),

    startStreaming: () => set({ streaming: true, streamingContent: '', error: null }),

    appendToken: (token) =>
        set((state) => ({ streamingContent: state.streamingContent + token })),

    addToolCall: (toolName) =>
        set((state) => ({
            streamingContent: state.streamingContent + `\n\n⚙️ *${toolName}...*\n\n`,
        })),

    finishStreaming: (pendingConfirm = false) =>
        set((state) => ({
            streaming: false,
            pendingConfirm,
            messages: [
                ...state.messages,
                { role: 'assistant', content: state.streamingContent },
            ],
            streamingContent: '',
        })),

    setError: (error) => set({ streaming: false, error }),

    clearPendingConfirm: () => set({ pendingConfirm: false }),

    clearMessages: () =>
        set({ messages: [], streamingContent: '', pendingConfirm: false }),
}))

export default useChatStore
