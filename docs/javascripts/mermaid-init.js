// Initialize mermaid.js for MkDocs Material (free tier)
// The fence_code_format wraps content in <pre class="mermaid"><code>
// Mermaid.js expects content directly in <pre class="mermaid">
// This script extracts the code content and re-initializes mermaid

document.addEventListener("DOMContentLoaded", function () {
  // Find all mermaid pre blocks and extract code content
  document.querySelectorAll("pre.mermaid code").forEach(function (codeEl) {
    var pre = codeEl.parentElement;
    pre.textContent = codeEl.textContent;
  });

  // Initialize mermaid with dark theme
  if (typeof mermaid !== "undefined") {
    mermaid.initialize({
      startOnLoad: true,
      theme: "dark",
      securityLevel: "loose",
    });
  }
});
