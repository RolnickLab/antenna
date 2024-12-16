import * as Sentry from '@sentry/react'
import 'nova-ui-kit/dist/style.css'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './app'
import './index.css'

if (process.env.NODE_ENV !== 'development') {
  Sentry.init({
    dsn: 'https://bdacb11d18ccce7135e11de82e017632@o4503927026876416.ingest.sentry.io/4505909755838464',
    environment: process.env.NODE_ENV,
  })
}

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement)
root.render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
