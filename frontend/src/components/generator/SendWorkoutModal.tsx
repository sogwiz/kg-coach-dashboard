/**
 * SendWorkoutModal — modal for sending a workout to a client with a message.
 *
 * Pre-populates a friendly 3-sentence message based on the workout, which
 * the coach can edit before sending.
 */

import { useState, useEffect } from "react";
import type { WorkoutVariant } from "../../lib/api";
import { fetchPreviewMessage, postSendWorkout } from "../../lib/api";

interface SendWorkoutModalProps {
  memberId: string;
  memberName: string;
  variant: WorkoutVariant;
  isOpen: boolean;
  onClose: () => void;
  onSent: () => void;
}

export function SendWorkoutModal({
  memberId,
  memberName,
  variant,
  isOpen,
  onClose,
  onSent,
}: SendWorkoutModalProps) {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch pre-populated message when modal opens
  useEffect(() => {
    if (isOpen && memberId && variant) {
      setLoading(true);
      setError(null);
      fetchPreviewMessage(memberId, variant.variant_id)
        .then((res) => {
          setMessage(res.message);
        })
        .catch(() => {
          setError("Couldn't generate message preview");
          // Fallback message
          const firstName = memberName.split(" ")[0];
          setMessage(
            `Hey ${firstName}! Here's your ${variant.plan.total_minutes}-minute workout for today. ` +
            `We're focusing on ${variant.optimizes_for.toLowerCase()} with ${variant.plan.warmup.length + variant.plan.main.length + variant.plan.cooldown.length} exercises. ` +
            `Let me know if you have any questions!`
          );
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, memberId, variant, memberName]);

  const handleSend = async () => {
    setSending(true);
    setError(null);
    try {
      await postSendWorkout(memberId, variant.variant_id, message);
      onSent();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send workout");
    } finally {
      setSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-indigo-500 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">
                Send Workout to {memberName}
              </h3>
              <p className="text-sm text-indigo-100 mt-0.5">
                {variant.label} · {variant.plan.total_minutes} min
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-white/80 hover:text-white transition-colors"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Message to client
          </label>

          {loading ? (
            <div className="h-32 bg-slate-100 rounded-lg animate-pulse flex items-center justify-center">
              <span className="text-sm text-slate-400">
                Generating message...
              </span>
            </div>
          ) : (
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={5}
              className="w-full px-4 py-3 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
              placeholder="Add a friendly message..."
            />
          )}

          {error && (
            <p className="mt-2 text-sm text-red-600">{error}</p>
          )}

          <p className="mt-3 text-xs text-slate-500">
            This message will be sent along with the workout details.
          </p>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={sending || loading || !message.trim()}
            className="px-5 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {sending ? (
              <>
                <svg
                  className="animate-spin w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeDasharray="30 70"
                  />
                </svg>
                Sending...
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
                Send Workout
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
