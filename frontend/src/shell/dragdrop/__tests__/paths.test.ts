import { describe, expect, test, vi } from "vitest";
import {
  DEFAULT_MAX_BATCH_ITEMS,
  DEFAULT_MAX_FILE_BYTES,
  SUPPORTED_IMPORT_EXTENSIONS,
  planDrop,
  validateDropPath,
  type DropFs,
  type DropFsStat,
} from "../paths";

function fileStat(bytes: number): DropFsStat {
  return {
    bytes,
    isFile: true,
    isDirectory: false,
    isSymlink: false,
    isSocket: false,
    isFifo: false,
  };
}

function dirStat(): DropFsStat {
  return { bytes: 0, isFile: false, isDirectory: true, isSymlink: false, isSocket: false, isFifo: false };
}

function socketStat(): DropFsStat {
  return { bytes: 0, isFile: false, isDirectory: false, isSymlink: false, isSocket: true, isFifo: false };
}

function fifoStat(): DropFsStat {
  return { bytes: 0, isFile: false, isDirectory: false, isSymlink: false, isSocket: false, isFifo: true };
}

function symlinkStat(): DropFsStat {
  return { bytes: 0, isFile: false, isDirectory: false, isSymlink: true, isSocket: false, isFifo: false };
}

/** Build a fake DropFs from a stat table plus an optional symlink target table. */
function makeFs(
  stats: Record<string, DropFsStat | "error">,
  links: Record<string, string> = {},
): DropFs {
  return {
    stat: vi.fn(async (path: string) => {
      const entry = stats[path];
      if (!entry || entry === "error") throw new Error(`ENOENT: no such file: ${path}`);
      return entry;
    }),
    realpath: vi.fn(async (path: string) => {
      if (path in links) return links[path];
      throw new Error(`EINVAL: not a symlink: ${path}`);
    }),
  };
}

const PNG = fileStat(1024);
const FS = makeFs({ "/home/u/pics/a.png": PNG });

describe("SUPPORTED_IMPORT_EXTENSIONS", () => {
  test("mirrors the middleware converter allowlist", () => {
    expect(SUPPORTED_IMPORT_EXTENSIONS).toEqual(
      expect.arrayContaining(["png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "avif"]),
    );
    expect(SUPPORTED_IMPORT_EXTENSIONS).toHaveLength(8);
  });
});

describe("validateDropPath", () => {
  test("accepts a normal png and reports normalized path and size", async () => {
    const fs = makeFs({ "/home/u/pics/a.png": PNG });
    const result = await validateDropPath("/home/u/./pics/a.png", { fs });
    expect(result.ok).toBe(true);
    expect(result.path).toBe("/home/u/pics/a.png");
    expect(result.bytes).toBe(1024);
  });

  test("matches extensions case-insensitively", async () => {
    const fs = makeFs({ "/x/B.PNG": PNG, "/x/c.JpEg": PNG });
    expect((await validateDropPath("/x/B.PNG", { fs })).ok).toBe(true);
    expect((await validateDropPath("/x/c.JpEg", { fs })).ok).toBe(true);
  });

  test("rejects relative paths", async () => {
    const result = await validateDropPath("pics/a.png", { fs: FS });
    expect(result).toMatchObject({ ok: false, reason: "path is not absolute" });
  });

  test("rejects tilde-home paths (not expanded)", async () => {
    const result = await validateDropPath("~/pics/a.png", { fs: FS });
    expect(result.ok).toBe(false);
  });

  test("rejects paths containing NUL bytes", async () => {
    const result = await validateDropPath("/x/a.png\u0000.png", { fs: FS });
    expect(result.reason).toBe("path contains a NUL byte");
  });

  test("rejects empty paths", async () => {
    expect((await validateDropPath("", { fs: FS })).ok).toBe(false);
  });

  test("rejects parent traversal even though absolute paths cannot escape", async () => {
    const result = await validateDropPath("/home/u/../secret.png", { fs: FS });
    expect(result).toMatchObject({ ok: false, reason: "parent traversal (`..`) is not allowed" });
    expect(FS.stat).not.toHaveBeenCalled();
  });

  test("rejects a trailing `..` basename", async () => {
    const result = await validateDropPath("/home/u/pics/..", { fs: FS });
    expect(result.ok).toBe(false);
  });

  test("rejects the filesystem root and bare directories as filenames", async () => {
    expect((await validateDropPath("/", { fs: FS })).reason).toBe("missing filename");
    expect((await validateDropPath("/home/u/pics/", { fs: FS })).ok).toBe(false);
  });

  test("rejects dotfile-looking names with no stem", async () => {
    const result = await validateDropPath("/x/.png", { fs: FS });
    expect(result).toMatchObject({ ok: false, reason: "missing filename stem" });
  });

  test("rejects unsupported and missing extensions", async () => {
    expect((await validateDropPath("/x/notes.txt", { fs: FS })).reason).toBe('unsupported extension ".txt"');
    expect((await validateDropPath("/x/noext", { fs: FS })).reason).toBe("missing extension");
  });

  test("honours a custom extension override", async () => {
    const fs = makeFs({ "/x/vector.svg": PNG });
    const opts = { fs, extensions: ["svg"] };
    expect((await validateDropPath("/x/vector.svg", opts)).ok).toBe(true);
    expect((await validateDropPath("/x/photo.png", opts)).ok).toBe(false);
  });

  test("rejects directories, sockets and FIFOs", async () => {
    const fs = makeFs({
      "/x/dir.png": dirStat(),
      "/x/sock.png": socketStat(),
      "/x/pipe.png": fifoStat(),
    });
    expect((await validateDropPath("/x/dir.png", { fs })).reason).toBe("directories cannot be imported");
    expect((await validateDropPath("/x/sock.png", { fs })).reason).toBe("sockets cannot be imported");
    expect((await validateDropPath("/x/pipe.png", { fs })).reason).toBe("FIFOs cannot be imported");
  });

  test("rejects non-regular files", async () => {
    const fs = makeFs({ "/x/block.png": fileStat(1) });
    // Corrupt the fake: isFile false but not any of the named kinds.
    const weird = { ...fileStat(1), isFile: false };
    (fs.stat as ReturnType<typeof vi.fn>).mockResolvedValueOnce(weird);
    const result = await validateDropPath("/x/block.png", { fs });
    expect(result.reason).toBe("not a regular file");
  });

  test("surfaces stat failures as rejections", async () => {
    const fs = makeFs({ "/x/gone.png": "error" });
    const result = await validateDropPath("/x/gone.png", { fs });
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("filesystem error");
    expect(result.reason).toContain("ENOENT");
  });

  test("enforces the default 512 MiB ceiling", async () => {
    const big = fileStat(DEFAULT_MAX_FILE_BYTES + 1);
    const fs = makeFs({ "/x/big.png": big, "/x/ok.png": fileStat(DEFAULT_MAX_FILE_BYTES) });
    const tooBig = await validateDropPath("/x/big.png", { fs });
    expect(tooBig.ok).toBe(false);
    expect(tooBig.reason).toContain("exceeds");
    expect((await validateDropPath("/x/ok.png", { fs })).ok).toBe(true);
  });

  test("honours a custom maxBytes", async () => {
    const fs = makeFs({ "/x/mid.png": fileStat(2048) });
    expect((await validateDropPath("/x/mid.png", { fs, maxBytes: 1024 })).ok).toBe(false);
    expect((await validateDropPath("/x/mid.png", { fs, maxBytes: 4096 })).ok).toBe(true);
  });

  describe("symlinks", () => {
    test("accepts a symlink whose resolved target passes all checks", async () => {
      const fs = makeFs({ "/tmp/link.png": symlinkStat(), "/data/real.png": fileStat(42) }, {
        "/tmp/link.png": "/data/real.png",
      });
      const result = await validateDropPath("/tmp/link.png", { fs });
      expect(result.ok).toBe(true);
      expect(result.path).toBe("/data/real.png");
      expect(result.bytes).toBe(42);
      expect(fs.realpath).toHaveBeenCalledWith("/tmp/link.png");
    });

    test("rejects a symlink whose resolved target flips the extension", async () => {
      const fs = makeFs({ "/tmp/link.png": symlinkStat() }, { "/tmp/link.png": "/etc/secret.txt" });
      const result = await validateDropPath("/tmp/link.png", { fs });
      expect(result.ok).toBe(false);
      expect(result.reason).toContain("symlink target rejected");
      expect(result.reason).toContain('unsupported extension ".txt"');
    });

    test("rejects a symlink resolving to a directory", async () => {
      const fs = makeFs(
        { "/tmp/link.png": symlinkStat(), "/data/dir.png": dirStat() },
        { "/tmp/link.png": "/data/dir.png" },
      );
      const result = await validateDropPath("/tmp/link.png", { fs });
      expect(result.ok).toBe(false);
      expect(result.reason).toContain("directories cannot be imported");
    });

    test("rejects a symlink whose resolved target exceeds maxBytes", async () => {
      const fs = makeFs(
        { "/tmp/link.png": symlinkStat(), "/data/real.png": fileStat(10) },
        { "/tmp/link.png": "/data/real.png" },
      );
      const result = await validateDropPath("/tmp/link.png", { fs, maxBytes: 5 });
      expect(result.ok).toBe(false);
      expect(result.reason).toContain("exceeds");
    });

    test("rejects chained symlinks past the depth guard", async () => {
      const stats: Record<string, DropFsStat> = {};
      const links: Record<string, string> = {};
      for (let i = 0; i < 12; i += 1) {
        stats[`/l${i}.png`] = symlinkStat();
        links[`/l${i}.png`] = `/l${i + 1}.png`;
      }
      stats["/l12.png"] = fileStat(1);
      const fs = makeFs(stats, links);
      const result = await validateDropPath("/l0.png", { fs });
      expect(result.ok).toBe(false);
      expect(result.reason).toContain("too many levels of symbolic links");
    });

    test("surfaces realpath failures as rejections", async () => {
      const fs = makeFs({ "/tmp/broken.png": symlinkStat() });
      const result = await validateDropPath("/tmp/broken.png", { fs });
      expect(result.ok).toBe(false);
      expect(result.reason).toContain("realpath failed");
    });
  });
});

describe("planDrop", () => {
  const MANY = 300;
  const table: Record<string, DropFsStat> = {};
  for (let i = 0; i < MANY; i += 1) table[`/pics/${i}.png`] = fileStat(10);
  const fs = makeFs(table);

  test("plans an empty batch", async () => {
    const plan = await planDrop([], { fs });
    expect(plan.accepted).toEqual([]);
    expect(plan.rejected).toEqual([]);
  });

  test("dedups after normalization and reports the duplicate", async () => {
    const plan = await planDrop(["/pics/0.png", "/pics/./0.png", "/pics/1.png"], { fs });
    expect(plan.accepted.map((d) => d.path)).toEqual(["/pics/0.png", "/pics/1.png"]);
    expect(plan.rejected).toEqual([{ path: "/pics/./0.png", reason: "duplicate of /pics/0.png" }]);
  });

  test("caps the accepted batch at maxItems (default 256) and refuses the rest", async () => {
    const paths = Array.from({ length: MANY }, (_, i) => `/pics/${i}.png`);
    const plan = await planDrop(paths, { fs });
    expect(plan.accepted).toHaveLength(DEFAULT_MAX_BATCH_ITEMS);
    expect(plan.rejected).toHaveLength(MANY - DEFAULT_MAX_BATCH_ITEMS);
    expect(plan.rejected[0].reason).toContain("batch item cap 256");
  });

  test("honours a custom maxItems cap", async () => {
    const plan = await planDrop(["/pics/0.png", "/pics/1.png", "/pics/2.png"], { fs, maxItems: 2 });
    expect(plan.accepted).toHaveLength(2);
    expect(plan.rejected).toHaveLength(1);
    expect(plan.rejected[0].path).toBe("/pics/2.png");
  });

  test("enforces the total-bytes budget and latches once exhausted", async () => {
    const budgetFs = makeFs({
      "/b/a.png": fileStat(60),
      "/b/b.png": fileStat(30),
      "/b/c.png": fileStat(30),
      "/b/d.png": fileStat(10),
    });
    const plan = await planDrop(["/b/a.png", "/b/b.png", "/b/c.png", "/b/d.png"], {
      fs: budgetFs,
      maxTotalBytes: 100,
    });
    expect(plan.accepted.map((d) => d.path)).toEqual(["/b/a.png", "/b/b.png"]);
    expect(plan.rejected[0]).toEqual({
      path: "/b/c.png",
      reason: "batch byte budget 100 exceeded",
    });
    // Latched: d.png would fit in the remaining 10 bytes but is refused anyway.
    expect(plan.rejected[1]).toEqual({
      path: "/b/d.png",
      reason: "batch byte budget exhausted by earlier items",
    });
  });

  test("rejected entries keep the raw offered path and per-file failures pass through", async () => {
    const plan = await planDrop(["nope.png", "/pics/0.png"], { fs });
    expect(plan.accepted).toHaveLength(1);
    expect(plan.rejected).toEqual([{ path: "nope.png", reason: "path is not absolute" }]);
  });

  test("runs validation through the per-file maxBytesPerFile option", async () => {
    const plan = await planDrop(["/pics/0.png"], { fs, maxBytesPerFile: 5 });
    expect(plan.accepted).toHaveLength(0);
    expect(plan.rejected[0].reason).toContain("exceeds");
  });
});
