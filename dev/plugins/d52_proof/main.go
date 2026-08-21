// Command d52_proof is the D52 proof plugin.
//
// A tiny, dependency-free Go binary that exists to prove the plugin process
// protocol (D52, docs/moon/roadmaps/development_tool.md) is genuinely
// language-neutral. The host spawns it as `d52_proof --stdio` (Grok lock #8:
// `manifest.entry.command` is the argv; the host appends `--stdio`) and speaks
// JSON-RPC 2.0 over that process's stdin/stdout. The JSON-RPC methods are the
// frozen contract; this binary answers the only two every plugin must
// implement -- initialize and list_artifacts -- plus a ping liveness probe.
//
// It is a *proof*, not a product plugin: list_artifacts returns a single
// synthetic Artifact (the {kind, name, path, meta} shape from #410) to prove
// structured payloads survive the process boundary. No Python import, no
// Image-Toolkit package required.
//
// Build: `go build -o bin/d52_proof .` (see README.md).
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
)

const (
	protocolVersion = "1"
	serverName      = "d52_proof"
	serverVersion   = "0.1.0"
)

// request is one JSON-RPC 2.0 message from the host. An absent "id" makes it a
// notification (no response). id is kept as raw JSON so string/number/null
// ids round-trip untouched.
type request struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// response is the JSON-RPC 2.0 reply written to stdout.
type response struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

// marshal is a response serializer; all response types are marshal-safe, so a
// failure here is unrecoverable (panic in the test/debug path only).
func marshal(v response) string {
	b, err := json.Marshal(v)
	if err != nil {
		panic(fmt.Sprintf("d52_proof: marshal response: %v", err))
	}
	return string(b)
}

// handle processes one raw JSON-RPC line and returns the response line to
// write (ok=true) or nothing (ok=false for notifications).
func handle(raw string) (out string, ok bool) {
	var req request
	if err := json.Unmarshal([]byte(raw), &req); err != nil {
		return marshal(response{
			JSONRPC: "2.0",
			ID:      json.RawMessage("null"),
			Error:   &rpcError{Code: -32700, Message: "parse error"},
		}), true
	}
	if req.ID == nil {
		return "", false // notification: no response
	}
	switch req.Method {
	case "initialize":
		return marshal(response{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"protocolVersion": protocolVersion,
				"capabilities":    map[string]any{"artifacts": true},
				"serverInfo":      map[string]any{"name": serverName, "version": serverVersion},
			},
		}), true
	case "list_artifacts":
		return marshal(response{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"artifacts": []map[string]any{
					{
						"kind": "report",
						"name": "d52_proof",
						"path": nil,
						"meta": map[string]any{
							"language": "go",
							"purpose":  "D52 language-neutrality proof",
						},
					},
				},
			},
		}), true
	case "ping":
		return marshal(response{JSONRPC: "2.0", ID: req.ID, Result: map[string]any{}}), true
	default:
		return marshal(response{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   &rpcError{Code: -32601, Message: fmt.Sprintf("method not found: %s", req.Method)},
		}), true
	}
}

func main() {
	stdio := flag.Bool("stdio", false, "speak JSON-RPC 2.0 over stdin/stdout (the host appends this flag)")
	flag.Parse()
	if !*stdio {
		fmt.Fprintln(os.Stderr, "d52_proof: --stdio is required (Grok lock #8: the host appends it)")
		os.Exit(2)
	}

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 64*1024), 1<<20)
	out := bufio.NewWriter(os.Stdout)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		resp, respond := handle(line)
		if !respond {
			continue
		}
		out.WriteString(resp + "\n")
		out.Flush()
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "d52_proof: stdin error: %v\n", err)
		os.Exit(1)
	}
}