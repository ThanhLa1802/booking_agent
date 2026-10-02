// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatBubble from '../components/ChatBubble'

describe('ChatBubble', () => {
    it('renders user message with correct text', () => {
        render(<ChatBubble role="user" content="Hello world" />)
        expect(screen.getByText('Hello world')).toBeInTheDocument()
    })

    it('renders assistant markdown content', () => {
        render(<ChatBubble role="assistant" content="**Bold text**" />)
        // react-markdown renders bold as <strong>
        expect(screen.getByText('Bold text').tagName).toBe('STRONG')
    })

    it('renders content while streaming', () => {
        render(
            <ChatBubble role="assistant" content="typing..." streaming={true} />
        )
        // Content is rendered while streaming (alongside a blinking cursor)
        expect(screen.getByText('typing...')).toBeInTheDocument()
    })
})
