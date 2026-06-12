export type SSEEventType =
  | 'node_started'
  | 'node_completed'
  | 'candidates_preview'
  | 'round_completed'
  | 'round_error'
  | 'mutation_completed'
  | 'mutation_error'
  | 'realization_completed'
  | 'realization_error'
  | 'token_usage';

export interface TokenUsageBreakdown {
  input: number;
  output: number;
  calls: number;
}

export interface TokenUsage {
  round: number;
  total_input: number;
  total_output: number;
  total_cached: number;
  total_tokens: number;
  by_model: Record<string, { input: number; output: number; cached: number; calls: number }>;
  by_phase: Record<string, TokenUsageBreakdown & { model: string }>;
  estimated_cost_usd: number;
  is_estimate: boolean;
}

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

export type SSEHandler = (event: SSEEvent) => void;

export async function readSSEStream(
  response: Response,
  onEvent: SSEHandler,
  onDone?: () => void,
): Promise<void> {
  if (!response.body) {
    throw new Error('Response body is null');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double newlines
      const parts = buffer.split('\n\n');
      // Keep the last (possibly incomplete) part in the buffer
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        if (!part.trim()) continue;

        let eventType: string | null = null;
        let dataStr: string | null = null;

        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice('event: '.length).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice('data: '.length).trim();
          }
        }

        if (eventType && dataStr) {
          try {
            const parsedData = JSON.parse(dataStr) as Record<string, unknown>;
            onEvent({ type: eventType as SSEEventType, data: parsedData });
          } catch {
            // Ignore unparseable data lines
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
    onDone?.();
  }
}
