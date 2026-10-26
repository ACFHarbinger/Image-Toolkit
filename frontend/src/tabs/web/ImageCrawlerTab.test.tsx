import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import ImageCrawlerTab from "./ImageCrawlerTab";

afterEach(() => {
  cleanup();
});

test("ImageCrawlerTab renders and runs crawl via hostClient", async () => {
  const showModal = vi.fn();
  const hostClient = {
    crawlerCrawl: vi.fn().mockResolvedValue({
      success: true,
      crawler_type: "general",
      total_downloaded: 15,
      download_dir: "/tmp/crawler_downloads",
      errors: [],
      elapsed_seconds: 0.5,
    }),
    crawlerListSupported: vi.fn().mockResolvedValue({
      types: ["general", "danbooru"],
      boards: ["Danbooru API"],
      action_templates: ["Find Parent Link (<a>)"],
    }),
  };

  render(<ImageCrawlerTab showModal={showModal} hostClient={hostClient as any} />);

  // List supported called on mount
  await waitFor(() => {
    expect(hostClient.crawlerListSupported).toHaveBeenCalled();
  });

  // Enter URL
  const urlInput = screen.getByPlaceholderText(/Target URL/i);
  fireEvent.change(urlInput, { target: { value: "https://example.com/gallery" } });

  // Run crawler
  const runBtn = screen.getByRole("button", { name: /Run Crawler/i });
  fireEvent.click(runBtn);

  await waitFor(() => {
    expect(hostClient.crawlerCrawl).toHaveBeenCalledWith(
      expect.objectContaining({
        crawler_type: "general",
        url: "https://example.com/gallery",
      })
    );
  });

  expect(await screen.findByTestId("crawler-status-banner")).toHaveTextContent(
    /Completed: 15 items downloaded/i
  );
});

test("ImageCrawlerTab handles crawl failure from hostClient", async () => {
  const showModal = vi.fn();
  const hostClient = {
    crawlerCrawl: vi.fn().mockResolvedValue({
      success: false,
      crawler_type: "danbooru",
      total_downloaded: 0,
      download_dir: "/tmp/crawler_downloads",
      errors: ["Connection timed out"],
      elapsed_seconds: 1.2,
    }),
    crawlerListSupported: vi.fn().mockResolvedValue({
      types: ["general", "danbooru"],
      boards: ["Danbooru API"],
      action_templates: [],
    }),
  };

  render(<ImageCrawlerTab showModal={showModal} hostClient={hostClient as any} />);

  // Switch to Danbooru
  const select = screen.getAllByRole("combobox")[0];
  fireEvent.change(select, { target: { value: "Image Board Crawler (Danbooru API)" } });

  // Run crawler
  const runBtn = screen.getByRole("button", { name: /Run Crawler/i });
  fireEvent.click(runBtn);

  await waitFor(() => {
    expect(hostClient.crawlerCrawl).toHaveBeenCalledWith(
      expect.objectContaining({
        crawler_type: "danbooru",
      })
    );
  });

  expect(await screen.findByTestId("crawler-status-banner")).toHaveTextContent(
    /Error: Connection timed out/i
  );
});
