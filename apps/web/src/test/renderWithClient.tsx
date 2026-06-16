import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";

/** retry 끄고 staleTime 0인 테스트 전용 QueryClient. */
export function makeTestClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

/** UI를 새 QueryClientProvider로 감싸 렌더. client를 함께 반환해 캐시 검사 가능. */
export function renderWithClient(ui: ReactElement, options?: RenderOptions) {
  const client = makeTestClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...render(ui, { wrapper, ...options }) };
}
