export function windowRole(): string {
  if (typeof window === "undefined") {
    return "main";
  }
  return new URLSearchParams(window.location.search).get("window") ?? "main";
}
