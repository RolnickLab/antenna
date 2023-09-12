import '@testing-library/jest-dom'
import { LocalStorageMock } from 'utils/test'

Object.defineProperty(window, 'localStorage', { value: new LocalStorageMock() })
