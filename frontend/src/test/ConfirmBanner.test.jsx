// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ConfirmBanner from '../components/ConfirmBanner'

describe('ConfirmBanner', () => {
    it('renders confirm and cancel buttons', () => {
        render(<ConfirmBanner onConfirm={vi.fn()} onCancel={vi.fn()} />)
        expect(screen.getByRole('button', { name: /xác nhận/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /hủy/i })).toBeInTheDocument()
    })

    it('calls onConfirm when confirm clicked', () => {
        const onConfirm = vi.fn()
        render(<ConfirmBanner onConfirm={onConfirm} onCancel={vi.fn()} />)
        fireEvent.click(screen.getByRole('button', { name: /xác nhận/i }))
        expect(onConfirm).toHaveBeenCalledOnce()
    })

    it('calls onCancel when cancel clicked', () => {
        const onCancel = vi.fn()
        render(<ConfirmBanner onConfirm={vi.fn()} onCancel={onCancel} />)
        fireEvent.click(screen.getByRole('button', { name: /hủy/i }))
        expect(onCancel).toHaveBeenCalledOnce()
    })
})
