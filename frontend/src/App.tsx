import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { WorkstationPage } from "./pages/WorkstationPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<WorkstationPage />} />
          <Route path="/investigations" element={<WorkstationPage />} />
          <Route path="/investigations/new" element={<WorkstationPage />} />
          <Route path="/investigations/:id" element={<WorkstationPage />} />
          <Route path="*" element={<WorkstationPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
