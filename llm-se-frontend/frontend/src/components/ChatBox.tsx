import { useState, useRef, useEffect } from "react";
import type { KeyboardEvent, FormEvent } from "react";
import ReactMarkdown from "react-markdown";

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

interface AnswerResponse {
  type: "answer";
  data: {
    answer: string;
    sources: Source[];
  };
}

interface NoInfoResponse {
  type: "no_info";
  reason: string;
}

type QueryResponse = AnswerResponse | NoInfoResponse;

export default function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

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
      const res = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          request_id: requestId,
          query,
        }),
      });

      if (!res.ok) throw new Error();

      const data: QueryResponse = await res.json();

      setMessages((prev) => {
        const cleaned = prev.filter((m) => m.id !== requestId);

        if (data.type === "answer") {
          return [
            ...cleaned,
            {
              id: generateRequestId(),
              role: "assistant",
              content: data.data.answer,
              // keep only FIRST source, ignore similarity
              sources: data.data.sources?.slice(0, 1),
            },
          ];
        }

        return [
          ...cleaned,
          {
            id: generateRequestId(),
            role: "system",
            content: "No relevant information found.",
          },
        ];
      });
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.content !== "Thinking…"),
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
  <ReactMarkdown>{m.content}</ReactMarkdown>
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
    background:
      "linear-gradient(180deg, #0f1115 0%, #151922 100%)",
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
