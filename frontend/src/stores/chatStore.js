import { create } from 'zustand'

/**
 * chatStore — conversation history + SSE streaming state
 */
const useChatStore = create((set, get) => ({
    messages: [],          // [{ role: 'user'|'assistant', content: string, toolCalls?: [] }]
    streaming: false,      // true while SSE is open
    streamingContent: '',  // partial assistant message being built
    activeTools: [],       // tool names currently executing (shown as chips)
    pendingConfirm: false, // true when agent returns confirmation-required warning
    sessionId: null,
    error: null,

    setSessionId: (sessionId) => set({ sessionId }),

    addUserMessage: (content) =>
        set((state) => ({
            messages: [...state.messages, { role: 'user', content }],
        })),

    startStreaming: () => set({ streaming: true, streamingContent: '', activeTools: [], error: null }),

    appendToken: (token) =>
        set((state) => ({ streamingContent: state.streamingContent + token })),

    // Replace entire streaming content — used when doneContent supersedes intermediate tokens
    // (e.g., "please wait..." token replaced by the actual schedule plan)
    setStreamingContent: (content) => set({ streamingContent: content }),

    addToolCall: (toolName) =>
        set((state) => ({
            activeTools: [...state.activeTools.filter(t => t !== toolName), toolName],
        })),

    removeToolCall: (toolName) =>
        set((state) => ({
            activeTools: state.activeTools.filter(t => t !== toolName),
        })),

    finishStreaming: (pendingConfirm = false) =>
        set((state) => ({
            streaming: false,
            activeTools: [],
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
