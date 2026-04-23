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

    it('shows spinner when streaming=true', () => {
        const { container } = render(
            <ChatBubble role="assistant" content="typing..." streaming={true} />
        )
        // MUI CircularProgress renders an svg role="progressbar"
        expect(container.querySelector('[role="progressbar"]') || container.querySelector('svg')).toBeTruthy()
    })
})
