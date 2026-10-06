import React from 'react'
import ReactDOM from 'react-dom/client'
import '@mantine/core/styles.css'
import './styles.css'
import './app.css'
import './brand-overrides.css'
import './public-typography.css'
import './card-polish.css'
import './dashboard-layout-polish.css'
import './dashboard-formation-tweaks.css'
import './account-support.css'
import './teacher-onboarding.css'
import './toast.css'
import App from './App'
import { ToastViewport } from './ui/toast'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <>
      <App />
      <ToastViewport />
    </>
  </React.StrictMode>,
)
