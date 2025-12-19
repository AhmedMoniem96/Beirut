"""Reusable helpers for consistent error handling and user notifications."""
from __future__ import annotations

import sys
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple, TypeVar

from ..core.paths import LOG_DIR

NotifyFn = Callable[[str, str, str], None]
T = TypeVar("T")


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _format_trace(exc: BaseException, tb) -> str:
    return "".join(traceback.format_exception(type(exc), exc, tb or exc.__traceback__))


def log_exception(
    context: str,
    exc: BaseException,
    *,
    tb=None,
    extra: Optional[str] = None,
) -> Path:
    """Persist the traceback to the log directory and return the log path."""

    _ensure_log_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%I%M%S%p")
    safe_context = context.replace("/", "-").replace(" ", "_")
    path = LOG_DIR / f"{timestamp}-{safe_context}.log"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"Timestamp: {timestamp}\n")
        fh.write(f"Context: {context}\n")
        if extra:
            fh.write(f"Details: {extra}\n")
        fh.write("\n")
        fh.write(_format_trace(exc, tb))
    return path


def console_notifier(title: str, message: str, details: str, *, stream=None) -> None:
    stream = stream or sys.stderr
    stream.write(f"{title}: {message}\n")
    if details:
        stream.write(f"{details}\n")


def report_exception(
    context: str,
    exc: BaseException,
    *,
    notifier: Optional[NotifyFn] = None,
    tb=None,
    extra: Optional[str] = None,
    heading: str = "حدث خطأ غير متوقع",
) -> Path:
    """Record the exception and surface a user-friendly message."""

    log_path = log_exception(context, exc, tb=tb, extra=extra)
    message = f"حدث خطأ غير متوقع أثناء {context}."
    details = f"تم حفظ تفاصيل الخطأ في:\n{log_path}"
    if notifier:
        notifier(heading, message, details)
    else:
        console_notifier(heading, message, details)
    return log_path


def guarded_call(
    context: str,
    func: Callable[..., T],
    *args,
    notifier: Optional[NotifyFn] = None,
    heading: str = "حدث خطأ غير متوقع",
    **kwargs,
) -> Tuple[bool, Optional[T]]:
    """Execute *func* and trap errors into the shared reporting path."""

    try:
        return True, func(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        report_exception(context, exc, notifier=notifier, heading=heading)
        return False, None


def install_global_exception_handlers(
    context: str,
    *,
    notifier: Optional[NotifyFn] = None,
    heading: str = "حدث خطأ غير متوقع",
) -> None:
    """Replace sys and threading excepthooks so crashes surface gracefully."""

    def _hook(exctype, value, tb):  # pragma: no cover - exercised via GUI runtime
        report_exception(context, value, notifier=notifier, tb=tb, heading=heading)

    sys.excepthook = _hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):  # pragma: no cover - requires threads
            report_exception(
                f"{context} (thread)",
                args.exc_value,
                notifier=notifier,
                tb=args.exc_traceback,
                heading=heading,
            )

        threading.excepthook = _thread_hook


@contextmanager
def handled_section(
    context: str,
    *,
    notifier: Optional[NotifyFn] = None,
    heading: str = "حدث خطأ غير متوقع",
) -> Iterator[None]:
    """Context manager variant to wrap complex flows."""

    try:
        yield
    except Exception as exc:  # pragma: no cover - defensive
        report_exception(context, exc, notifier=notifier, heading=heading)
        raise
