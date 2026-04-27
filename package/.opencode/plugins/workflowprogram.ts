import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const WORKFLOWPROGRAM_PACKAGE_PLUGIN_ID = "workflowprogram-package-bridge"
const DEFAULT_PYTHON = process.platform === "win32" ? "python" : "python3"

function normalizePath(input: string): string {
  return process.platform === "win32" ? input.replace(/\//g, "\\") : input
}

function normalizeExecutable(input: string): string {
  if (path.isAbsolute(input)) {
    return path.resolve(input)
  }
  if (input.includes("/") || input.includes("\\")) {
    return path.resolve(input)
  }
  return input
}

function resolvePluginDirectory(): string {
  const meta = import.meta as ImportMeta & { dir?: string }
  if (meta.dir) {
    return path.resolve(meta.dir)
  }
  return path.dirname(fileURLToPath(import.meta.url))
}

function readPackageRootFromManifest(dir: string): string | null {
  const manifestPath = path.join(dir, ".workflowprogram", "package", "install-manifest.json")
  if (!fs.existsSync(manifestPath)) {
    return null
  }
  try {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"))
    const sourceRoot = typeof manifest.source_package_root === "string" ? manifest.source_package_root : ""
    if (sourceRoot && fs.existsSync(sourceRoot)) {
      return path.resolve(sourceRoot)
    }
  } catch {
    // ignore
  }
  return null
}

function derivePackageRoot(pluginDirectory: string, currentDirectory: string): string {
  const fromManifest = readPackageRootFromManifest(currentDirectory)
  if (fromManifest) {
    return fromManifest
  }
  const normalized = path.resolve(pluginDirectory)
  if (path.basename(normalized) === "plugins") {
    const parent = path.dirname(normalized)
    if (path.basename(parent) === ".opencode") {
      return path.dirname(parent)
    }
    return parent
  }
  return path.resolve(currentDirectory)
}

function detectRuntimeRoot(packageRoot: string): string {
  return path.join(packageRoot, ".workflowprogram", "runtime")
}

function venvPythonPath(packageRoot: string): string | null {
  const candidates = [
    path.join(packageRoot, ".workflowprogram", ".venv", "Scripts", "python.exe"),
    path.join(packageRoot, ".workflowprogram", ".venv", "bin", "python"),
  ]
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate
    }
  }
  return null
}

function detectPythonExecutable(packageRoot: string): string {
  const manifestPath = path.join(packageRoot, ".workflowprogram", "package", "install-manifest.json")
  if (fs.existsSync(manifestPath)) {
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"))
      const manifestPython = typeof manifest.python_executable === "string" ? manifest.python_executable : ""
      if (manifestPython && fs.existsSync(manifestPython)) {
        return manifestPython
      }
    } catch {
      // Fall back to filesystem detection below.
    }
  }
  return venvPythonPath(packageRoot) || DEFAULT_PYTHON
}

function hostSmokeDir(): string | null {
  const raw = process.env.WORKFLOWPROGRAM_HOST_SMOKE_DIR || ""
  if (!raw) {
    return null
  }
  return path.resolve(raw)
}

function appendJsonl(pathname: string, payload: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(pathname), { recursive: true })
  fs.appendFileSync(pathname, `${JSON.stringify(payload)}\n`, "utf8")
}

function writeHostSmokeRecord(name: string, payload: Record<string, unknown>): void {
  const directory = hostSmokeDir()
  if (!directory) {
    return
  }
  fs.mkdirSync(directory, { recursive: true })
  fs.writeFileSync(path.join(directory, name), `${JSON.stringify(payload, null, 2)}\n`, "utf8")
}

function appendHostSmokeEvent(name: string, payload: Record<string, unknown>): void {
  const directory = hostSmokeDir()
  if (!directory) {
    return
  }
  appendJsonl(path.join(directory, name), payload)
}

function safePayload(value: unknown): unknown {
  try {
    return JSON.parse(JSON.stringify(value))
  } catch {
    return {
      preview: String(value),
    }
  }
}

function patchCommand(command: string, packageRoot: string, runtimeRoot: string, pythonExecutable: string): string {
  const normalizedPackageRoot = normalizePath(packageRoot)
  const normalizedRuntimeRoot = normalizePath(runtimeRoot)
  const normalizedPythonExecutable = normalizePath(pythonExecutable)
  return command
    .replace(/\$\{WORKFLOWPROGRAM_PACKAGE_ROOT\}/g, normalizedPackageRoot)
    .replace(/\$WORKFLOWPROGRAM_PACKAGE_ROOT/g, normalizedPackageRoot)
    .replace(/\$\{WORKFLOWPROGRAM_RUNTIME_ROOT\}/g, normalizedRuntimeRoot)
    .replace(/\$WORKFLOWPROGRAM_RUNTIME_ROOT/g, normalizedRuntimeRoot)
    .replace(/\$\{WORKFLOWPROGRAM_PYTHON\}/g, normalizedPythonExecutable)
    .replace(/\$WORKFLOWPROGRAM_PYTHON/g, normalizedPythonExecutable)
}

export const WorkflowProgramPackageBridge = async (context: {
  client?: {
    app?: {
      log?: (payload: unknown) => Promise<void>
    }
  }
  directory: string
}) => {
  const pluginDirectory = resolvePluginDirectory()
  const packageRoot = path.resolve(
    process.env.WORKFLOWPROGRAM_PACKAGE_ROOT || derivePackageRoot(pluginDirectory, context.directory),
  )
  const runtimeRoot = path.resolve(
    process.env.WORKFLOWPROGRAM_RUNTIME_ROOT || detectRuntimeRoot(packageRoot),
  )
  const pythonExecutable = normalizeExecutable(
    process.env.WORKFLOWPROGRAM_PYTHON || detectPythonExecutable(packageRoot),
  )
  writeHostSmokeRecord("plugin-loaded.json", {
    pluginId: WORKFLOWPROGRAM_PACKAGE_PLUGIN_ID,
    packageRoot,
    runtimeRoot,
    pythonExecutable,
    pid: process.pid,
    timestamp: new Date().toISOString(),
  })

  return {
    event: async ({ event }: { event?: Record<string, unknown> }) => {
      if (!event || typeof event.type !== "string") {
        return
      }
      if (event.type === "command.executed") {
        appendHostSmokeEvent("command-events.jsonl", {
          type: event.type,
          timestamp: new Date().toISOString(),
          event: safePayload(event),
        })
        return
      }
      if (event.type === "session.created" || event.type === "session.error" || event.type === "session.status") {
        appendHostSmokeEvent("session-events.jsonl", {
          type: event.type,
          timestamp: new Date().toISOString(),
          event: safePayload(event),
        })
      }
    },

    "tool.execute.before": async (input: any, output: any) => {
      if (input?.tool !== "bash") {
        return
      }
      if (!output?.args?.command) {
        return
      }

      output.args.command = patchCommand(output.args.command, packageRoot, runtimeRoot, pythonExecutable)
      appendHostSmokeEvent("runtime-before.jsonl", {
        timestamp: new Date().toISOString(),
        tool: input?.tool ?? null,
        command: output.args.command,
      })
    },

    "tool.execute.after": async (input: any, output: any) => {
      if (input?.tool !== "bash") {
        return
      }
      const command = input?.args?.command || ""
      const normalizedRuntimeRoot = normalizePath(runtimeRoot)
      // Engine-in-cache model (deepseek): only .workflowprogram/runtime/ is relevant
      if (
        !command.includes(normalizedRuntimeRoot) &&
        !command.includes(".workflowprogram/runtime/")
      ) {
        return
      }

      appendHostSmokeEvent("runtime-after.jsonl", {
        timestamp: new Date().toISOString(),
        tool: input?.tool ?? null,
        command,
        exitCode: output?.exitCode ?? null,
      })

      await context.client?.app?.log?.({
        body: {
          service: WORKFLOWPROGRAM_PACKAGE_PLUGIN_ID,
          level: output?.exitCode === 0 ? "info" : "warn",
          message: "WorkflowProgram runtime command executed",
          extra: {
            exitCode: output?.exitCode ?? null,
            packageRoot,
            runtimeRoot,
            pythonExecutable,
          },
        },
      })
    },
  }
}
