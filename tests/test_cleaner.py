#!/usr/bin/env python3
"""Regression checks for WorkflowProgram maintenance cleanup."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "package"
CLEANER_SCRIPT = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "cleaner.py"
DEPLOY_SCRIPT = PACKAGE_ROOT / ".workflowprogram" / "runtime" / "package-deploy.py"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _args(**kwargs: Any) -> Any:
    defaults = {
        "target_root": ".",
        "package_root": None,
        "pycache": False,
        "pytest_cache": False,
        "dist": False,
        "node_modules": False,
        "runs": False,
        "older_than": None,
        "keep_last": None,
        "include_failed_runs": False,
        "all_safe": False,
        "yes": False,
        "json": True,
    }
    defaults.update(kwargs)
    return type("Args", (), defaults)()


def assert_cleaner_dry_run_does_not_delete() -> None:
    cleaner = _load_module(CLEANER_SCRIPT, "workflowprogram_cleaner_test_dry")
    with tempfile.TemporaryDirectory(prefix="wp-clean-dry-") as tmp:
        target = Path(tmp)
        cache = target / "pkg" / "__pycache__"
        cache.mkdir(parents=True)
        pyc = cache / "x.pyc"
        pyc.write_bytes(b"cache")
        args = _args(target_root=str(target), pycache=True)
        plan = cleaner.build_plan(args)
        result = cleaner.apply_plan(plan, yes=False)
        cleaner.write_reports(result)
        if not pyc.exists():
            raise AssertionError("dry-run deleted pycache")
        if not (target / ".workflowprogram" / "maintenance" / "clean-report.json").is_file():
            raise AssertionError("dry-run did not write clean report")


def assert_cleaner_deletes_pycache_with_yes() -> None:
    cleaner = _load_module(CLEANER_SCRIPT, "workflowprogram_cleaner_test_apply")
    with tempfile.TemporaryDirectory(prefix="wp-clean-pycache-") as tmp:
        target = Path(tmp)
        cache = target / "pkg" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "x.pyc").write_bytes(b"cache")
        args = _args(target_root=str(target), pycache=True, yes=True)
        plan = cleaner.build_plan(args)
        result = cleaner.apply_plan(plan, yes=True)
        if cache.exists():
            raise AssertionError("pycache directory was not deleted")
        if "pkg/__pycache__" not in result.get("deleted", []):
            raise AssertionError(f"deleted list did not include pycache: {result}")


def assert_cleaner_protects_design_and_package() -> None:
    cleaner = _load_module(CLEANER_SCRIPT, "workflowprogram_cleaner_test_protect")
    with tempfile.TemporaryDirectory(prefix="wp-clean-protect-") as tmp:
        target = Path(tmp)
        (target / ".workflowprogram" / "design").mkdir(parents=True)
        (target / ".workflowprogram" / "design" / "workflow-spec.yaml").write_text("meta: {}\n", encoding="utf-8")
        (target / ".workflowprogram" / "package" / "runtime").mkdir(parents=True)
        (target / ".workflowprogram" / "managed-files.json").write_text("{}\n", encoding="utf-8")
        args = _args(target_root=str(target), all_safe=True, yes=True)
        plan = cleaner.build_plan(args)
        result = cleaner.apply_plan(plan, yes=True)
        protected = {item["path"] for item in result["candidates"] if item["risk"] == "protected"}
        if ".workflowprogram/design" not in protected:
            raise AssertionError(f"design path was not protected: {result}")
        if not (target / ".workflowprogram" / "design" / "workflow-spec.yaml").is_file():
            raise AssertionError("protected design file was deleted")


def assert_cleaner_prunes_runs_conservatively() -> None:
    cleaner = _load_module(CLEANER_SCRIPT, "workflowprogram_cleaner_test_runs")
    with tempfile.TemporaryDirectory(prefix="wp-clean-runs-") as tmp:
        target = Path(tmp)
        runs = target / ".workflowprogram" / "runs"
        for name, verdict in (("001-old", "PASS"), ("002-mid", "PASS"), ("003-new", "PASS")):
            run = runs / name
            run.mkdir(parents=True)
            (run / "state.json").write_text(f'{{"status":"completed","verdict":"{verdict}"}}\n', encoding="utf-8")
        args = _args(target_root=str(target), runs=True, keep_last=1, yes=True)
        plan = cleaner.build_plan(args)
        result = cleaner.apply_plan(plan, yes=True)
        if not (runs / "003-new").is_dir():
            raise AssertionError("newest run was not protected")
        if (runs / "001-old").exists() or (runs / "002-mid").exists():
            raise AssertionError(f"older runs were not pruned: {result}")


def assert_clean_bootstrap_cache_keeps_active_version() -> None:
    deploy = _load_module(DEPLOY_SCRIPT, "workflowprogram_deploy_clean_cache_test")
    with tempfile.TemporaryDirectory(prefix="wp-clean-cache-") as tmp:
        root = Path(tmp)
        global_root = root / "global"
        cache_root = root / "cache"
        active = cache_root / "packages" / "active" / "package"
        old = cache_root / "packages" / "old" / "package"
        active.mkdir(parents=True)
        old.mkdir(parents=True)
        manifest = global_root / ".workflowprogram" / "bootstrap" / "bootstrap-manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            '{"cache_root":"%s","cache_package_root":"%s"}\n' % (cache_root.as_posix(), active.as_posix()),
            encoding="utf-8",
        )
        result = deploy.clean_bootstrap_cache(
            target_root=str(global_root),
            cache_root=str(cache_root),
            keep_last=0,
            remove_version=None,
            yes=True,
        )
        if not active.exists():
            raise AssertionError("active cache version was deleted")
        if old.exists():
            raise AssertionError(f"old cache version was not deleted: {result}")


def main() -> int:
    assert_cleaner_dry_run_does_not_delete()
    assert_cleaner_deletes_pycache_with_yes()
    assert_cleaner_protects_design_and_package()
    assert_cleaner_prunes_runs_conservatively()
    assert_clean_bootstrap_cache_keeps_active_version()
    print("maintenance cleaner regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
