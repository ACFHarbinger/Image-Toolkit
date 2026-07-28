"""`web` command group: image crawling."""

from __future__ import annotations

import sys

from backend.src.web.crawlers.image_crawler import ImageCrawler


def dispatch_web(args: dict) -> None:
    command = args.get("web_command")
    if command == "crawl":
        try:
            config = {
                "url": args.get("query"),
                "download_dir": args.get("output"),
                "limit": args.get("limit"),
                "type": "general",
                "headless": True,
                "browser": "chrome",
            }

            crawler = ImageCrawler(config)

            # Connect signals to print to terminal for CLI usage
            crawler.on_status.connect(lambda msg: print(f"[*] {msg}"))
            crawler.on_finished.connect(lambda msg: print(f"[+] {msg}"))

            print(f"🚀 Starting web crawler for: {config['url']}")
            crawler.run()
        except ImportError as e:
            print(f"❌ Error: Required modules not found: {e}", file=sys.stderr)
        except Exception as e:
            print(f"❌ Web crawler failed: {e}", file=sys.stderr)
    else:
        print(f"Web command '{command}' not yet connected to CLI", file=sys.stderr)
