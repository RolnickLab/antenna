import '@testing-library/jest-dom'
import { LocalStorageMock } from 'utils/testHelpers'

Object.defineProperty(window, 'localStorage', { value: new LocalStorageMock() })

jest.mock('axios')
