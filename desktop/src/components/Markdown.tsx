import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import s from "./Markdown.module.css";

/**
 * Assistant-turn renderer: GFM plus syntax highlighting, matching the web UI's
 * plugin set (`remark-gfm` + `rehype-highlight`).
 *
 * Links are forced to open externally. Inside a Tauri webview a plain
 * navigation would replace the app itself, which is unrecoverable — there is no
 * back button in a decorated window with no chrome.
 */
export function Markdown({ content }: { content: string }) {
  return (
    <div className={`${s.markdown} selectable`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              onClick={(e) => {
                // `target=_blank` is not honored consistently by the webview;
                // opening through the shell is the reliable path.
                e.preventDefault();
                if (href) void openExternal(href);
              }}
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

async function openExternal(url: string): Promise<void> {
  try {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  } catch {
    // Plain-browser dev fallback.
    window.open(url, "_blank", "noreferrer");
  }
}
