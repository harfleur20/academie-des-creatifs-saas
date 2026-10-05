import React from 'react'
import ReactDOM from 'react-dom/client'
import '@mantine/core/styles.css'
import './styles.css'
import './app.css'
import './brand-overrides.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
