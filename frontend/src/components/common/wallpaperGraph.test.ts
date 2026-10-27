import { expect, test } from "vitest";
import { moveQueuePath, readGraphPayload } from "./wallpaperGraph";

test("dropping an image moves it onto the other monitor", () => {
  const next = moveQueuePath(
    { "DP-1": ["/a.png", "/b.png"], "HDMI-1": [] },
    "/b.png",
    "DP-1",
    "HDMI-1",
  );
  expect(next["DP-1"]).toEqual(["/a.png"]);
  expect(next["HDMI-1"]).toEqual(["/b.png"]);
});

test("a graph payload round-trips the monitor and the path", () => {
  expect(readGraphPayload("DP-1\n/wall/sky.png")).toEqual({ monitorId: "DP-1", path: "/wall/sky.png" });
});
