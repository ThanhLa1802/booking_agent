import { create } from 'zustand'

/**
 * examStore — catalog browsing state (instrument, grade, style, selected slot)
 */
const useExamStore = create((set) => ({
    instruments: [],
    grades: [],
    slots: [],
    selectedInstrument: null,
    selectedGrade: null,
    selectedStyle: null,   // 'classical_jazz' | 'rock_pop' | 'theory'
    selectedSlot: null,
    loading: false,
    error: null,

    setInstruments: (instruments) => set({ instruments }),
    setGrades: (grades) => set({ grades }),
    setSlots: (slots) => set({ slots }),
    selectInstrument: (instrument) => set({ selectedInstrument: instrument }),
    selectGrade: (grade) => set({ selectedGrade: grade }),
    selectStyle: (style) => set({ selectedStyle: style }),
    selectSlot: (slot) => set({ selectedSlot: slot }),
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
    reset: () =>
        set({
            selectedInstrument: null,
            selectedGrade: null,
            selectedStyle: null,
            selectedSlot: null,
        }),
}))

export default useExamStore
