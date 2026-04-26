"use client";

import { useState, useEffect, FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Database, ArrowRight, Clock, Code2, Table as TableIcon, ChevronDown, ChevronUp, Terminal, Copy, Check } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";

// Custom theme for SyntaxHighlighter to match our minimal look
const minimalTheme: any = {
  'code[class*="language-"]': {
    color: 'var(--foreground)',
    background: 'none',
    fontFamily: 'var(--font-mono), monospace',
    fontSize: '0.875rem',
    lineHeight: '1.5',
  },
  'comment': { color: 'var(--muted)' },
  'keyword': { color: 'var(--foreground)', fontWeight: 'bold' },
  'string': { color: 'var(--muted)' },
  'function': { color: 'var(--foreground)' },
  'operator': { color: 'var(--foreground)' },
  'number': { color: 'var(--muted)' },
};

interface SchemaColumn {
  name: string;
  type: string;
  description: string | null;
}

interface SchemaTable {
  table_name: string;
  description: string;
  columns: SchemaColumn[];
}

interface QueryResponse {
  question: string;
  sql: string;
  explanation: string;
  tables_used: string[];
  latency_ms: number;
  warning?: string;
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const [schemas, setSchemas] = useState<SchemaTable[]>([]);
  const [showSchemas, setShowSchemas] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (response?.sql) {
      navigator.clipboard.writeText(response.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  useEffect(() => {
    fetch("http://localhost:8000/schema")
      .then((res) => res.json())
      .then((data) => setSchemas(data))
      .catch((err) => console.error("Failed to fetch schemas", err));
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });

      if (!res.ok) throw new Error(`Error: ${res.statusText}`);
      const data = await res.json();
      setResponse(data);
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 md:p-12">
      <div className="w-full max-w-3xl space-y-12">
        
        {/* Header */}
        <header className="space-y-2">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase text-muted"
          >
            <Database className="w-3 h-3" />
            <span>SQL GEN — v1.0</span>
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-3xl md:text-4xl font-semibold tracking-tight"
          >
            Translate language to logic.
          </motion.h1>
        </header>

        {/* Search Bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <form onSubmit={handleSubmit} className="relative group">
            <div className="relative flex items-center bg-card border border-border rounded-xl overflow-hidden shadow-sm transition-all focus-within:border-foreground/30 focus-within:shadow-md">
              <Search className="w-5 h-5 text-muted ml-4" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask your database anything..."
                className="w-full bg-transparent border-none text-foreground placeholder-muted px-4 py-5 outline-none text-lg"
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="mr-3 p-2 text-muted hover:text-foreground transition-colors disabled:opacity-30"
              >
                {loading ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                  >
                    <Clock className="w-5 h-5" />
                  </motion.div>
                ) : (
                  <ArrowRight className="w-5 h-5" />
                )}
              </button>
            </div>
          </form>
        </motion.div>

        {/* Content Area */}
        <div className="space-y-8">
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-sm text-red-500 bg-red-500/5 border border-red-500/10 px-4 py-3 rounded-lg flex items-center gap-2"
              >
                <Terminal className="w-4 h-4" />
                <span>{error}</span>
              </motion.div>
            )}

            {response && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-6"
              >
                {/* Result Sections */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs font-medium uppercase tracking-widest text-muted">
                    <div className="flex items-center gap-2">
                      <Code2 className="w-3 h-3" />
                      <span>Generated SQL</span>
                    </div>
                    <span>{response.latency_ms}ms</span>
                  </div>
                  
                  <div className="relative bg-card border border-border rounded-xl shadow-sm group">
                    <button
                      onClick={handleCopy}
                      className="absolute top-4 right-4 p-2 rounded-md bg-card/80 backdrop-blur-sm hover:bg-muted/20 text-muted hover:text-foreground transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 z-10"
                      title="Copy SQL"
                    >
                      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <div className="p-6 font-mono text-sm overflow-x-auto">
                      <SyntaxHighlighter
                        language="sql"
                        style={minimalTheme}
                        customStyle={{ background: 'transparent', padding: 0 }}
                      >
                        {response.sql}
                      </SyntaxHighlighter>
                    </div>
                  </div>
                </div>

                <div className="grid md:grid-cols-5 gap-6">
                  <div className="md:col-span-3 space-y-4">
                    <div className="text-xs font-medium uppercase tracking-widest text-muted">Explanation</div>
                    <p className="text-foreground/80 leading-relaxed text-sm">
                      {response.explanation}
                    </p>
                  </div>
                  <div className="md:col-span-2 space-y-4">
                    <div className="text-xs font-medium uppercase tracking-widest text-muted">Scope</div>
                    <div className="flex flex-wrap gap-2">
                      {response.tables_used.map((table, i) => (
                        <span key={i} className="px-2 py-1 bg-muted/10 text-muted rounded text-[10px] font-mono border border-border/50">
                          {table}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Schema Explorer */}
          <div className="pt-8 border-t border-border/50">
            <button 
              onClick={() => setShowSchemas(!showSchemas)}
              className="group flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-muted hover:text-foreground transition-colors"
            >
              {showSchemas ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              <span>Schema Explorer</span>
              <span className="opacity-0 group-hover:opacity-100 transition-opacity ml-2 px-1.5 py-0.5 bg-muted/10 rounded text-[9px]">{schemas.length} tables found</span>
            </button>
            
            <AnimatePresence>
              {showSchemas && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden mt-6"
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border/50 border border-border rounded-lg overflow-hidden">
                    {schemas.map((schema, idx) => (
                      <div key={idx} className="bg-card p-6 space-y-4">
                        <div className="flex items-center gap-2">
                          <TableIcon className="w-4 h-4 text-muted" />
                          <h4 className="font-semibold text-sm">{schema.table_name}</h4>
                        </div>
                        <p className="text-xs text-muted leading-relaxed line-clamp-2">{schema.description}</p>
                        <div className="space-y-1.5 pt-2">
                          {schema.columns.map((col, cidx) => (
                            <div key={cidx} className="flex items-center justify-between text-[11px] font-mono">
                              <span className="text-foreground/70">{col.name}</span>
                              <span className="text-muted/50">{col.type}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </div>
    </main>
  );
}
