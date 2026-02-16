import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AdminAuthProvider } from '@/contexts/AdminAuthContext';

// Create a custom render function that includes providers
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  withRouter?: boolean;
  withQueryClient?: boolean;
  withAdminAuth?: boolean;
}

export function customRender(
  ui: ReactElement,
  {
    withRouter = true,
    withQueryClient = true,
    withAdminAuth = false,
    ...renderOptions
  }: CustomRenderOptions = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  function Wrapper({ children }: { children: React.ReactNode }) {
    let content = children;

    if (withQueryClient) {
      content = (
        <QueryClientProvider client={queryClient}>
          {content}
        </QueryClientProvider>
      );
    }

    if (withAdminAuth) {
      content = <AdminAuthProvider>{content}</AdminAuthProvider>;
    }

    if (withRouter) {
      content = <BrowserRouter>{content}</BrowserRouter>;
    }

    return <>{content}</>;
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
}

// Re-export everything from testing library
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
export { customRender as render };
