import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';
import GenreManagement from './components/GenreManagement';
import PatternLibraryBrowser from './views/PatternLibraryBrowser';
import AppShell from './components/AppShell';

const queryClient = new QueryClient();

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded focus:px-3 focus:py-2 focus:text-xs focus:font-medium"
      style={{ background: 'var(--accent-primary)', color: 'var(--surface-0)' }}
    >
      Skip to main content
    </a>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SkipLink />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route element={<AppShell />}>
            <Route path="/genres" element={<GenreManagement />} />
            <Route path="/patterns" element={<PatternLibraryBrowser />} />
            <Route path="/session/:id" element={<SessionWorkspace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  );
}
