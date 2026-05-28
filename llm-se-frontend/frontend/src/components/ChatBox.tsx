import { useState, useRef, useEffect } from "react";
import type { KeyboardEvent, FormEvent } from "react";
import ReactMarkdown from "react-markdown";

import { API_BASE, authHeaders } from "../api/client";

interface Source {
  source: string;
  similarity: number;
}

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: Source[];
}


export default function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const generateRequestId = () =>
    `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  const sendMessage = async () => {
    const query = input.trim();
    if (!query || isLoading) return;

    const token = localStorage.getItem("token");
    if (!token) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateRequestId(),
          role: "system",
          content: "Authentication required. Please log in.",
        },
      ]);
      return;
    }

    const requestId = generateRequestId();

    setMessages((prev) => [
      ...prev,
      { id: generateRequestId(), role: "user", content: query },
      { id: requestId, role: "assistant", content: "Thinking…" },
    ]);

    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/query/stream`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          request_id: requestId,
          query,
        }),
      });

      if (!res.ok) {
        throw new Error("Query failed");
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      if (reader) {
        // Remove "Thinking..." placeholder
        setMessages((prev) => prev.filter((m) => m.id !== requestId));
        setStreamingMsgId(requestId);

        let assistantMessage: Message = {
          id: requestId,
          role: "assistant",
          content: "",
          sources: [],
        };

        let tokensSinceRender = 0;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const cleanLine = line.trim();
            if (!cleanLine) continue;

            if (cleanLine.startsWith("data: ")) {
              const dataStr = cleanLine.slice(6);
              if (dataStr === "[DONE]") {
                continue;
              }

              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.type === "metadata") {
                  assistantMessage.sources = parsed.sources?.slice(0, 1);
                  setMessages((prev) => {
                    const other = prev.filter((m) => m.id !== requestId);
                    return [...other, { ...assistantMessage }];
                  });
                } else if (parsed.type === "token") {
                  assistantMessage.content += parsed.content;
                  tokensSinceRender++;
                  // Yield every 2 tokens so React can re-render progressively
                  if (tokensSinceRender >= 2) {
                    setMessages((prev) => {
                      const other = prev.filter((m) => m.id !== requestId);
                      return [...other, { ...assistantMessage }];
                    });
                    tokensSinceRender = 0;
                    await new Promise((r) => setTimeout(r, 16));
                  }
                } else if (parsed.type === "no_info") {
                  setMessages((prev) => {
                    const other = prev.filter((m) => m.id !== requestId);
                    return [
                      ...other,
                      {
                        id: generateRequestId(),
                        role: "system",
                        content: "No relevant information found.",
                      },
                    ];
                  });
                }
              } catch (err) {
                console.error("Error parsing SSE line:", err);
              }
            }
          }

          // Flush any remaining buffered tokens after this chunk
          if (tokensSinceRender > 0) {
            setMessages((prev) => {
              const other = prev.filter((m) => m.id !== requestId);
              return [...other, { ...assistantMessage }];
            });
            tokensSinceRender = 0;
          }
        }

        setStreamingMsgId(null);
      }
    } catch (err) {
      console.error(err);
      setStreamingMsgId(null);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== requestId),
        {
          id: generateRequestId(),
          role: "system",
          content: "An error occurred. Please try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage();
  };

  return (
    <div style={styles.container}>
      <div style={styles.messages}>
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              ...styles.row,
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                ...styles.bubble,
                ...(m.role === "user"
                  ? styles.user
                  : m.role === "assistant"
                  ? styles.assistant
                  : styles.system),
              }}
            >
              {m.role === "assistant" ? (
                <>
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                  {streamingMsgId === m.id && (
                    <span className="streaming-cursor">▊</span>
                  )}
                </>
              ) : (
                <div>{m.content}</div>
              )}

              {m.sources && m.sources.length > 0 && (
                <div style={styles.source}>
                  Source: {m.sources[0].source}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} style={styles.inputBar}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Sentinel…"
          disabled={isLoading}
          rows={2}
          style={styles.textarea}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          style={styles.send}
        >
          Send
        </button>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    background: "linear-gradient(180deg, #0f1115 0%, #151922 100%)",
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    letterSpacing: "0.2px",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "1.5rem",
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },
  row: {
    display: "flex",
    width: "100%",
  },
  bubble: {
    maxWidth: "72%",
    padding: "1rem 1.25rem",
    borderRadius: "8px",
    fontSize: "0.95rem",
    lineHeight: "1.6",
  },
  user: {
    backgroundColor: "#3b82f6",
    color: "#ffffff",
  },
  assistant: {
    backgroundColor: "rgba(31, 36, 48, 0.92)",
    color: "#e5e7eb",
    border: "1px solid #2d3342",
  },
  system: {
    backgroundColor: "rgba(148,163,184,0.12)",
    color: "#cbd5f5",
    fontStyle: "italic",
  },
  source: {
    marginTop: "0.75rem",
    paddingTop: "0.5rem",
    borderTop: "1px solid #2d3342",
    fontSize: "0.75rem",
    color: "#9ca3af",
  },
  inputBar: {
    display: "flex",
    gap: "0.75rem",
    padding: "1rem",
    borderTop: "1px solid #1f2430",
    backgroundColor: "#0f1115",
  },
  textarea: {
    flex: 1,
    padding: "0.75rem 1rem",
    fontSize: "0.9rem",
    backgroundColor: "#0f1115",
    border: "1px solid #2d3342",
    borderRadius: "6px",
    color: "#e5e7eb",
    resize: "none",
    outline: "none",
  },
  send: {
    padding: "0.75rem 1.5rem",
    fontSize: "0.9rem",
    fontWeight: 500,
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
  },
};
