package main

import (
	"encoding/json"
	"testing"
)

func decode(t *testing.T, line string) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(line), &m); err != nil {
		t.Fatalf("bad JSON response: %v\n%s", err, line)
	}
	return m
}

func TestInitializeHandshake(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","id":1,"method":"initialize"}`)
	if !ok {
		t.Fatal("expected a response")
	}
	m := decode(t, out)
	if m["id"] != float64(1) {
		t.Fatalf("id not echoed: %#v", m["id"])
	}
	result, _ := m["result"].(map[string]any)
	if result["protocolVersion"] != protocolVersion {
		t.Fatalf("protocolVersion = %#v, want %q", result["protocolVersion"], protocolVersion)
	}
	info, _ := result["serverInfo"].(map[string]any)
	if info["name"] != serverName || info["version"] != serverVersion {
		t.Fatalf("serverInfo = %#v", info)
	}
}

func TestListArtifactsReturnsStructuredPayload(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","id":"a1","method":"list_artifacts"}`)
	if !ok {
		t.Fatal("expected a response")
	}
	m := decode(t, out)
	if m["id"] != "a1" {
		t.Fatalf("string id not preserved: %#v", m["id"])
	}
	result, _ := m["result"].(map[string]any)
	artifacts, _ := result["artifacts"].([]any)
	if len(artifacts) != 1 {
		t.Fatalf("expected 1 artifact, got %d", len(artifacts))
	}
	art, _ := artifacts[0].(map[string]any)
	if art["kind"] != "report" || art["name"] != "d52_proof" {
		t.Fatalf("unexpected artifact: %#v", art)
	}
	meta, _ := art["meta"].(map[string]any)
	if meta["language"] != "go" {
		t.Fatalf("meta.language = %#v, want go", meta["language"])
	}
}

func TestPing(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","id":2,"method":"ping"}`)
	if !ok {
		t.Fatal("expected a response")
	}
	m := decode(t, out)
	if _, hasErr := m["error"]; hasErr {
		t.Fatalf("ping should not error: %#v", m)
	}
}

func TestUnknownMethod(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","id":3,"method":"nope"}`)
	if !ok {
		t.Fatal("expected a response")
	}
	m := decode(t, out)
	errObj, _ := m["error"].(map[string]any)
	if errObj["code"] != float64(-32601) {
		t.Fatalf("error code = %#v, want -32601", errObj["code"])
	}
}

func TestParseError(t *testing.T) {
	out, ok := handle(`{not json`)
	if !ok {
		t.Fatal("expected a response")
	}
	m := decode(t, out)
	if m["id"] != nil {
		t.Fatalf("parse-error id should be null, got %#v", m["id"])
	}
	errObj, _ := m["error"].(map[string]any)
	if errObj["code"] != float64(-32700) {
		t.Fatalf("error code = %#v, want -32700", errObj["code"])
	}
}

func TestNotificationNoResponse(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","method":"ping"}`)
	if ok || out != "" {
		t.Fatalf("notification must not produce a response, got %q (ok=%v)", out, ok)
	}
}

func TestNullIDIsNotANotification(t *testing.T) {
	out, ok := handle(`{"jsonrpc":"2.0","id":null,"method":"ping"}`)
	if !ok {
		t.Fatal("id:null is a request, not a notification")
	}
	if out == "" {
		t.Fatal("expected a response for id:null")
	}
}