import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BoardThemeProvider } from './contexts/ThemeContext'
import App from './App'
import './styles/globals.css'
// Note: Custom theme removed - using shadcn/ui theming instead

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BoardThemeProvider>
        <App />
      </BoardThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
