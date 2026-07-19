import {
  createContext,
  useContext,
  useEffect,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { useI18n } from "../i18n/I18n";
import {
  getWindowFrame,
  hideMainWindow,
  minimizeMainWindow,
  setWindowFrame,
  startMainWindowDragging,
  startMainWindowResize,
  toggleMaximizeMainWindow,
  type WindowFramePreference,
  type WindowResizeDirection,
} from "../native/window";
import s from "./WindowFrame.module.css";

interface WindowFrameContextValue {
  frame: WindowFramePreference;
  setFrame: (frame: WindowFramePreference) => Promise<void>;
}

const WindowFrameContext = createContext<WindowFrameContextValue | null>(null);

export function useWindowFrame(): WindowFrameContextValue {
  const value = useContext(WindowFrameContext);
  if (!value) throw new Error("useWindowFrame must be used inside <WindowFrame>");
  return value;
}

interface TitleBarProps {
  onHide?: () => void | Promise<void>;
  onMinimize?: () => void | Promise<void>;
  onToggleMaximize?: () => void | Promise<unknown>;
}

export function TitleBar({
  onHide = hideMainWindow,
  onMinimize = minimizeMainWindow,
  onToggleMaximize = toggleMaximizeMainWindow,
}: TitleBarProps) {
  const { t } = useI18n();
  const toggleFromBar = (event: MouseEvent<HTMLElement>) => {
    if (!(event.target as Element).closest("button")) void onToggleMaximize();
  };

  const dragFromBar = (event: MouseEvent<HTMLElement>) => {
    if (event.button !== 0 || (event.target as Element).closest("button")) return;
    event.preventDefault();
    void startMainWindowDragging();
  };

  return (
    <header
      className={s.titleBar}
      data-tauri-drag-region
      onMouseDown={dragFromBar}
      onDoubleClick={toggleFromBar}
    >
      <div className={s.controls}>
        <button
          type="button"
          className={`${s.control} ${s.minimize}`}
          aria-label={t("window.minimize")}
          title={t("window.minimize")}
          onClick={() => void onMinimize()}
        >
          <span aria-hidden="true">−</span>
        </button>
        <button
          type="button"
          className={`${s.control} ${s.maximize}`}
          aria-label={t("window.maximizeRestore")}
          title={t("window.maximizeRestore")}
          onClick={() => void onToggleMaximize()}
        >
          <span aria-hidden="true">◇</span>
        </button>
        <button
          type="button"
          className={`${s.control} ${s.hide}`}
          aria-label={t("window.hide")}
          title={t("window.hide")}
          onClick={() => void onHide()}
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>
      <span className={s.title} data-tauri-drag-region>Dax</span>
    </header>
  );
}

const RESIZE_HANDLES: Array<{
  direction: WindowResizeDirection;
  className: string;
}> = [
  { direction: "North", className: "resizeNorth" },
  { direction: "NorthEast", className: "resizeNorthEast" },
  { direction: "East", className: "resizeEast" },
  { direction: "SouthEast", className: "resizeSouthEast" },
  { direction: "South", className: "resizeSouth" },
  { direction: "SouthWest", className: "resizeSouthWest" },
  { direction: "West", className: "resizeWest" },
  { direction: "NorthWest", className: "resizeNorthWest" },
];

function ResizeHandles() {
  return RESIZE_HANDLES.map(({ direction, className }) => (
    <div
      key={direction}
      aria-hidden="true"
      className={`${s.resizeHandle} ${s[className]}`}
      onMouseDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        void startMainWindowResize(direction);
      }}
    />
  ));
}

export function WindowFrame({ children }: { children: ReactNode }) {
  const [frame, setFrameState] = useState<WindowFramePreference>("custom");

  useEffect(() => {
    void getWindowFrame().then(setFrameState).catch(() => undefined);
  }, []);

  const setFrame = async (next: WindowFramePreference) => {
    const applied = await setWindowFrame(next);
    setFrameState(applied);
  };

  return (
    <WindowFrameContext.Provider value={{ frame, setFrame }}>
      <div className={s.frame} data-frame={frame}>
        {frame === "custom" && (
          <>
            <TitleBar />
            <ResizeHandles />
          </>
        )}
        <div className={s.content}>{children}</div>
      </div>
    </WindowFrameContext.Provider>
  );
}
