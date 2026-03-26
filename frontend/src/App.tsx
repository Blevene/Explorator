import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/session/:id" element={<SessionWorkspace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
