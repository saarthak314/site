from dataclasses import dataclass
from threading import Condition


@dataclass(frozen=True)
class ReloadEvent:
  version: int
  kind: str
  message: str


class LiveReloadState:
  def __init__(self) -> None:
    self._condition = Condition()
    self._event = ReloadEvent(version=0, kind="ready", message="")

  @property
  def version(self) -> int:
    with self._condition:
      return self._event.version

  def publish(self, kind: str, message: str = "") -> ReloadEvent:
    with self._condition:
      self._event = ReloadEvent(
        version=self._event.version + 1,
        kind=kind,
        message=message,
      )
      self._condition.notify_all()
      return self._event

  def wait_for_update(
    self,
    version: int,
    *,
    timeout: float | None = None,
  ) -> ReloadEvent | None:
    with self._condition:
      changed = self._condition.wait_for(
        lambda: self._event.version > version,
        timeout=timeout,
      )
      return self._event if changed else None


LIVE_RELOAD_CLIENT = """(() => {
  const errorId = "__sitegen-error";
  const clearError = () => document.getElementById(errorId)?.remove();
  const showError = (message) => {
    clearError();
    const overlay = document.createElement("pre");
    overlay.id = errorId;
    overlay.textContent = message;
    overlay.style.cssText = "position:fixed;inset:auto 1rem 1rem;z-index:2147483647;max-height:45vh;overflow:auto;margin:0;padding:1rem;border:1px solid #fb4934;background:#1d2021;color:#fbf1c7;font:14px/1.5 monospace;white-space:pre-wrap;box-shadow:0 12px 32px #0008";
    document.body.append(overlay);
  };
  const reloadCss = () => {
    const links = [...document.querySelectorAll('link[rel="stylesheet"]')];
    if (!links.length) {
      location.reload();
      return;
    }
    clearError();
    for (const link of links) {
      const replacement = link.cloneNode();
      const url = new URL(link.href, location.href);
      url.searchParams.set("__sitegen", Date.now());
      replacement.href = url;
      replacement.addEventListener("load", () => link.remove(), { once: true });
      replacement.addEventListener("error", () => replacement.remove(), { once: true });
      link.after(replacement);
    }
  };
  const events = new EventSource("/__sitegen/events?version=__SITEGEN_VERSION__");
  events.addEventListener("css", reloadCss);
  events.addEventListener("reload", () => location.reload());
  events.addEventListener("build-error", (event) => {
    const payload = JSON.parse(event.data);
    showError(payload.message);
  });
})();"""


def inject_live_reload(html: str, version: int) -> str:
  client = LIVE_RELOAD_CLIENT.replace("__SITEGEN_VERSION__", str(version))
  markup = f'<script data-sitegen-live-reload="true">{client}</script>'
  closing_body = html.lower().rfind("</body>")
  if closing_body == -1:
    return f"{html}{markup}"
  return f"{html[:closing_body]}{markup}{html[closing_body:]}"
