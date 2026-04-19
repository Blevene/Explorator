import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';
import GenreManagement from './components/GenreManagement';
import PatternLibraryBrowser from './views/PatternLibraryBrowser';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/genres" element={<GenreManagement />} />
          <Route path="/patterns" element={<PatternLibraryBrowser />} />
          <Route path="/session/:id" element={<SessionWorkspace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  );
}
