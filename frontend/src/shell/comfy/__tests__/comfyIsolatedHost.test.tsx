import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ComfyIsolatedHost } from "../ComfyIsolatedHost";
import {
  buildComfyWebSocketUrl,
  checkEmbeddingCompatibility,
  getComfySandboxPermissions,
  openExternalBrowser,
  validateComfyOrigin,
} from "../comfySecurity";

afterEach(() => {
  cleanup();
});

describe("ComfyUI Origin & Security Validation (#890, S-04)", () => {
  it("permits local loopback origins only", () => {
    expect(validateComfyOrigin("http://127.0.0.1:8188").valid).toBe(true);
    expect(validateComfyOrigin("http://localhost:8188").valid).toBe(true);
    expect(validateComfyOrigin("http://[::1]:8188").valid).toBe(true);

    const remote = validateComfyOrigin("https://comfy.external-domain.com:8188");
    expect(remote.valid).toBe(false);
    expect(remote.error).toContain("must run on a local loopback interface");

    const credentials = validateComfyOrigin("http://admin:secret@127.0.0.1:8188");
    expect(credentials.valid).toBe(false);
    expect(credentials.error).toContain("must not contain embedded user credentials");

    const invalidProto = validateComfyOrigin("javascript:alert(1)");
    expect(invalidProto.valid).toBe(false);
  });

  it("builds the correct WebSocket queue endpoint", () => {
    expect(buildComfyWebSocketUrl("http://127.0.0.1:8188")).toBe("ws://127.0.0.1:8188/ws");
    expect(buildComfyWebSocketUrl("https://localhost:8443/app")).toBe("wss://localhost:8443/ws");
  });

  it("detects X-Frame-Options and CSP frame-ancestors restrictions", () => {
    const unprobed = checkEmbeddingCompatibility("http://127.0.0.1:8188");
    expect(unprobed.embeddable).toBe(false);
    expect(unprobed.checked).toBe(false);

    const clean = checkEmbeddingCompatibility("http://127.0.0.1:8188", {});
    expect(clean.embeddable).toBe(true);
    expect(clean.checked).toBe(true);
    expect(clean.wsUrl).toBe("ws://127.0.0.1:8188/ws");

    const deny = checkEmbeddingCompatibility("http://127.0.0.1:8188", {
      "x-frame-options": "DENY",
    });
    expect(deny.embeddable).toBe(false);
    expect(deny.reason).toContain("X-Frame-Options: DENY");

    const sameOrigin = checkEmbeddingCompatibility("http://127.0.0.1:8188", {
      "X-Frame-Options": "SAMEORIGIN",
    });
    expect(sameOrigin.embeddable).toBe(false);
    expect(sameOrigin.reason).toContain("X-Frame-Options: SAMEORIGIN");

    const cspBlock = checkEmbeddingCompatibility("http://127.0.0.1:8188", {
      "Content-Security-Policy": "frame-ancestors 'none'",
    });
    expect(cspBlock.embeddable).toBe(false);
    expect(cspBlock.reason).toContain("frame-ancestors");
  });

  it("generates strict sandbox permissions without top-navigation or native escape", () => {
    const perms = getComfySandboxPermissions();
    expect(perms).toContain("allow-scripts");
    expect(perms).toContain("allow-forms");
    expect(perms).toContain("allow-same-origin");
    expect(perms).toContain("allow-downloads");
    expect(perms).not.toContain("allow-top-navigation");
    expect(perms).not.toContain("allow-modals");
  });

  it("handles external browser fallback launch", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    await openExternalBrowser("http://127.0.0.1:8188");
    expect(openSpy).toHaveBeenCalledWith("http://127.0.0.1:8188", "_blank", "noopener,noreferrer");
    openSpy.mockRestore();
  });
});

describe("ComfyIsolatedHost Component (#890, S-04)", () => {
  it("renders isolated view with strict sandbox iframe when embeddable", async () => {
    render(<ComfyIsolatedHost comfyUrl="http://127.0.0.1:8188" probeHeaders={async () => ({})} />);

    expect(screen.getByTestId("comfy-isolated-host")).toBeInTheDocument();
    expect(screen.getByTestId("comfy-isolation-badge")).toHaveTextContent("Zero Native Privileges");

    const iframe = await screen.findByTestId("comfy-isolated-iframe");
    expect(iframe).toHaveAttribute("src", "http://127.0.0.1:8188");
    expect(iframe).toHaveAttribute("sandbox", getComfySandboxPermissions());
  });

  it("shows the fallback when the probe cannot read embedding headers", async () => {
    render(
      <ComfyIsolatedHost
        comfyUrl="http://127.0.0.1:8188"
        probeHeaders={async () => {
          throw new Error("probe failed");
        }}
      />,
    );
    expect(await screen.findByTestId("comfy-blocked-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("comfy-isolated-iframe")).not.toBeInTheDocument();
  });

  it("renders blocked banner and external fallback button when X-Frame-Options is DENY", () => {
    const onFallback = vi.fn();
    render(
      <ComfyIsolatedHost
        comfyUrl="http://127.0.0.1:8188"
        initialHeaders={{ "X-Frame-Options": "DENY" }}
        onFallbackToBrowser={onFallback}
      />,
    );

    expect(screen.getByTestId("comfy-blocked-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("comfy-isolated-iframe")).not.toBeInTheDocument();

    const fallbackBtn = screen.getByTestId("btn-fallback-external");
    fireEvent.click(fallbackBtn);
    expect(onFallback).toHaveBeenCalledWith("http://127.0.0.1:8188");
  });

  it("renders security error banner when a non-loopback remote URL is given", () => {
    render(<ComfyIsolatedHost comfyUrl="https://malicious-remote-server.com" />);
    expect(screen.getByTestId("comfy-error-banner")).toBeInTheDocument();
    expect(screen.getByText(/local loopback interface/)).toBeInTheDocument();
  });
});
