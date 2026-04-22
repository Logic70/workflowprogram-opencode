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

function derivePackageRoot(pluginDirectory: string, currentDirectory: string): string {
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
  const deployed = path.join(packageRoot, ".workflowprogram", "package", "runtime")
  if (fs.existsSync(deployed)) {
    return deployed
  }
  return path.join(packageRoot, ".workflowprogram", "runtime")
}

function venvPythonPath(packageRoot: string): string | null {
  const candidates = [
    path.join(packageRoot, ".workflowprogram", "package", ".venv", "Scripts", "python.exe"),
    path.join(packageRoot, ".workflowprogram", "package", ".venv", "bin", "python"),
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

export { WORKFLOWPROGRAM_PACKAGE_PLUGIN_ID }

export default async function workflowprogramPlugin(context: {
  client?: {
    app?: {
      log?: (payload: unknown) => Promise<void>
    }
  }
  directory: string
}) {
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

  return {
    "tool.execute.before": async (input: any, output: any) => {
      if (input?.tool !== "bash") {
        return
      }
      if (!output?.args?.command) {
        return
      }

      output.args.command = patchCommand(output.args.command, packageRoot, runtimeRoot, pythonExecutable)
    },

    "tool.execute.after": async (input: any, output: any) => {
      if (input?.tool !== "bash") {
        return
      }
      const command = input?.args?.command || ""
      const normalizedRuntimeRoot = normalizePath(runtimeRoot)
      if (
        !command.includes(normalizedRuntimeRoot) &&
        !command.includes(".workflowprogram/runtime/") &&
        !command.includes(".workflowprogram/package/runtime/")
      ) {
        return
      }

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
