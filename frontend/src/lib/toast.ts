// Thin wrapper around Sonner so a future swap (or test double) is a one-file change.
// All UI code should import from here, never from 'sonner' directly.
import { toast as sonnerToast, type ExternalToast } from 'sonner';

export type ToastOptions = ExternalToast;

export const toast = {
  success: (message: string, opts?: ToastOptions) => sonnerToast.success(message, opts),
  error: (message: string, opts?: ToastOptions) => sonnerToast.error(message, opts),
  info: (message: string, opts?: ToastOptions) => sonnerToast(message, opts),
};
