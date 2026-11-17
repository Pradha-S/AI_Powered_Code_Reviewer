import { useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const sampleCode = `def divide(a, b):
    return a / b

def get_user_name(user):
    return user["name"]

print(divide(10, 0))`;

function App() {
  const [code, setCode] = useState(sampleCode);
  const [language, setLanguage] = useState("Python");
  const [results, setResults] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState("Issues");
  const [filter, setFilter] = useState("All");
  const [copied, setCopied] = useState(false);

  const runAnalysis = async () => {
    setIsAnalyzing(true);
    setActiveTab("Issues");
    setFilter("All");

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, language }),
      });

      if (!response.ok) {
        throw new Error(`Analysis request failed (${response.status}).`);
      }

      setResults(await response.json());
    } catch (error) {
      setResults({
        issues: [],
        score: 0,
        error:
          error instanceof Error
            ? error.message
            : "Unable to connect to the analysis server.",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const visibleIssues =
    results?.issues.filter(
      (issue) => filter === "All" || issue.severity === filter
    ) ?? [];

  const highCount =
    results?.issues.filter((issue) => issue.severity === "High").length ?? 0;

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home">
          <span className="brand-icon">{"</>"}</span>
          <span>
            <strong>CodeGuard</strong>
            <small>AI CODE REVIEWER</small>
          </span>
        </a>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="nav-menu">
          <a className="nav-item active" href="#review">
            <span>⌘</span> Code Review
          </a>
          <button
            className="nav-item"
            onClick={() => {
              setResults(null);
              setCode(sampleCode);
            }}
          >
            <span>↻</span> New Analysis
          </button>
          <button
            className="nav-item"
            onClick={() => setActiveTab("Suggestions")}
          >
            <span>✧</span> Suggestions
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="plan-card">
            <div className="plan-icon">✦</div>
            <strong>AI Code Intelligence</strong>
            <p>Static checks now. AI-powered reviews coming next.</p>
            <div className="plan-progress">
              <span />
            </div>
            <small>PROJECT PROTOTYPE</small>
          </div>

          <div className="profile">
            <div className="avatar">PG</div>
            <div>
              <strong>Project Workspace</strong>
              <small>Developer</small>
            </div>
            <span className="profile-dots">···</span>
          </div>
        </div>
      </aside>

      <main className="main-content" id="review">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>Code Review</strong>
          </div>
          <div className="topbar-right">
            <span className="prototype-status">
              <span className="status-dot" /> Frontend Prototype
            </span>
            <button
              className="icon-button"
              title="Reset analysis"
              onClick={() => setResults(null)}
            >
              ↻
            </button>
          </div>
        </header>

        <section className="page-intro">
          <div>
            <div className="eyebrow">
              <span>✧</span> INTELLIGENT CODE ANALYSIS
            </div>
            <h1>Code Review</h1>
            <p>
              Find bugs, improve quality, and write better code with
              intelligent analysis.
            </p>
          </div>
          <div className="review-badge">
            <span className="review-badge-icon">⌘</span>
            <span>
              <strong>Smart Review</strong>
              <small>Analyze · Explain · Improve</small>
            </span>
          </div>
        </section>

        <section className="stats-grid">
          <StatCard
            label="CODE QUALITY"
            value={results ? `${results.score}/100` : "—"}
            note={results ? "Estimated prototype score" : "Run an analysis to begin"}
            icon="◈"
            color="purple"
          />
          <StatCard
            label="ISSUES FOUND"
            value={results ? results.issues.length : "—"}
            note={results ? "Potential issues detected" : "Awaiting code analysis"}
            icon="⚑"
            color="orange"
          />
          <StatCard
            label="HIGH SEVERITY"
            value={results ? highCount : "—"}
            note={results ? "Requires closer inspection" : "No results yet"}
            icon="△"
            color="red"
          />
          <StatCard
            label="LANGUAGE"
            value={language}
            note="Selected source language"
            icon="⌘"
            color="blue"
          />
        </section>

        <section className="editor-panel">
          <div className="panel-heading">
            <div>
              <h2>Source Code</h2>
              <p>Paste your code below to begin reviewing.</p>
            </div>
            <div className="editor-actions">
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                aria-label="Programming language"
              >
                <option>Python</option>
              </select>
              <button className="secondary-button" onClick={copyCode}>
                {copied ? "✓ Copied" : "▢ Copy"}
              </button>
              <button
                className="secondary-button"
                onClick={() => {
                  setCode("");
                  setResults(null);
                }}
              >
                Clear
              </button>
            </div>
          </div>

          <div className="code-editor">
            <div className="editor-gutter" aria-hidden="true">
              {code.split("\n").map((_, index) => (
                <div key={index}>{index + 1}</div>
              ))}
            </div>
            <textarea
              value={code}
              onChange={(event) => setCode(event.target.value)}
              spellCheck="false"
              aria-label="Source code editor"
              placeholder="Paste your source code here..."
            />
          </div>

          <div className="editor-footer">
            <span>
              <span className="status-dot" /> Ready to analyze
            </span>
            <span>
              {code.split("\n").length} lines · {code.length} characters
            </span>
          </div>

          <div className="analyze-row">
            <div className="analyze-hint">
              <span>✧</span> {isAnalyzing ? "Reviewing your code..." : "Review your code for potential issues."}
            </div>
            <button className="analyze-button" onClick={runAnalysis} disabled={isAnalyzing}>
              <span>⌕</span> {isAnalyzing ? "Analyzing..." : "Analyze Code"} <span>→</span>
            </button>
          </div>
        </section>

        <section className="results-panel">
          <div className="results-heading">
            <div>
              <h2>Analysis Results</h2>
              <p>
                {results
                  ? `${results.issues.length} potential issue(s) in your code`
                  : "Your findings will appear here after analysis."}
              </p>
            </div>
            {results && (
              <span className="completed-pill">
                <span className="status-dot" /> Analysis complete
              </span>
            )}
          </div>

          <div className="results-tabs">
            {["Issues", "Suggestions", "Overview"].map((tab) => (
              <button
                key={tab}
                className={`result-tab ${activeTab === tab ? "selected" : ""}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
                {tab === "Issues" && results && (
                  <span className="tab-count">{results.issues.length}</span>
                )}
              </button>
            ))}
          </div>

          {!results ? (
            <div className="empty-state">
              <div className="empty-icon">⌕</div>
              <strong>Ready when you are</strong>
              <p>Run Analyze Code to see potential bugs and improvements.</p>
            </div>
          ) : results.error && !results.issues.length ? (
            <div className="empty-state">
              <strong>Nothing to analyze yet</strong>
              <p>{results.error}</p>
            </div>
          ) : activeTab === "Overview" ? (
            <div className="overview-content">
              <div className="score-ring">
                <strong>{results.score}</strong>
                <span>/100</span>
              </div>
              <div>
                <h3>Code quality overview</h3>
                <p>
                  The prototype detected {results.issues.length} potential
                  issue(s). Review each finding and verify it against your
                  program's intended behavior.
                </p>
                <p className="disclaimer">
                  This score is a demonstration metric, not a validated
                  measure of code quality.
                </p>
              </div>
            </div>
          ) : activeTab === "Suggestions" ? (
            <div className="suggestions-content">
              {results.issues.length ? (
                results.issues.map((issue, index) => (
                  <div className="suggestion-row" key={`${issue.title}-${index}`}>
                    <span className="suggestion-bullet">✧</span>
                    <div>
                      <strong>{issue.title}</strong>
                      <p>{issue.fix}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="no-issues">No suggestions from the prototype checks.</p>
              )}
            </div>
          ) : (
            <>
              <div className="filter-row">
                {["All", "High", "Medium", "Low"].map((item) => (
                  <button
                    key={item}
                    className={`filter-chip ${filter === item ? "chosen" : ""}`}
                    onClick={() => setFilter(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>

              <div className="issues-list">
                {visibleIssues.length ? (
                  visibleIssues.map((issue, index) => (
                    <article className="issue-card" key={`${issue.title}-${index}`}>
                      <div className={`severity-icon ${issue.severity.toLowerCase()}`}>
                        {issue.severity === "High" ? "!" : issue.severity === "Medium" ? "△" : "i"}
                      </div>
                      <div className="issue-body">
                        <div className="issue-title-row">
                          <h3>{issue.title}</h3>
                          <span className={`severity-pill ${issue.severity.toLowerCase()}`}>
                            {issue.severity}
                          </span>
                        </div>
                        <p>{issue.description}</p>
                        <div className="issue-meta">
                          <span>{issue.category}</span>
                          <span>Line {issue.line}</span>
                        </div>
                        <div className="fix-box">
                          <strong><span>✧</span> Suggested improvement</strong>
                          <p>{issue.fix}</p>
                        </div>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="no-issues">
                    No issues match this filter. Try another severity.
                  </div>
                )}
              </div>
            </>
          )}

          <div className="results-disclaimer">
            <span>ⓘ</span>
            Python AST checks may miss bugs or report false positives. Always
            verify findings.
          </div>
        </section>

        <footer className="page-footer">
          <span>CodeGuard AI <span>·</span> PG Mini Project</span>
          <span>Built with React + Vite</span>
        </footer>
      </main>
    </div>
  );
}

function StatCard({ label, value, note, icon, color }) {
  return (
    <article className="stat-card">
      <div className="stat-top">
        <span>{label}</span>
        <span className={`stat-icon ${color}`}>{icon}</span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note}</div>
    </article>
  );
}

export default App;