export type SSEEventType =
  | 'node_started'
  | 'node_completed'
  | 'candidates_preview'
  | 'round_completed'
  | 'round_error';

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
