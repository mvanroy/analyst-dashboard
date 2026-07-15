"""Install app-style browser metadata for the standalone Buggins service."""
from __future__ import annotations

import streamlit.components.v1 as components


def install() -> None:
    components.html(
        """
        <script>
        (() => {
          const doc = window.parent.document;
          const upsertMeta = (name, content) => {
            let node = doc.head.querySelector(`meta[name="${name}"]`);
            if (!node) {
              node = doc.createElement("meta");
              node.setAttribute("name", name);
              doc.head.appendChild(node);
            }
            node.setAttribute("content", content);
          };
          const upsertLink = (rel, href) => {
            let node = doc.head.querySelector(`link[rel="${rel}"]`);
            if (!node) {
              node = doc.createElement("link");
              node.setAttribute("rel", rel);
              doc.head.appendChild(node);
            }
            node.setAttribute("href", href);
          };

          doc.title = "Buggins Daily Log";
          upsertMeta("theme-color", "#09182d");
          upsertMeta("mobile-web-app-capable", "yes");
          upsertMeta("apple-mobile-web-app-capable", "yes");
          upsertMeta("apple-mobile-web-app-status-bar-style", "black-translucent");
          upsertMeta("apple-mobile-web-app-title", "Buggins");
          upsertLink("manifest", "/app/static/buggins-manifest.webmanifest?v=1");
          upsertLink("apple-touch-icon", "/app/static/apple-touch-icon.png?v=1");
        })();
        </script>
        """,
        height=0,
        width=0,
    )
