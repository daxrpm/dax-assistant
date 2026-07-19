import appIcon from "../../src-tauri/icons/128x128.png";

export const APP_ICON_URL = appIcon;

export function AppIcon({
  size = 24,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <img
      src={appIcon}
      width={size}
      height={size}
      className={className}
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}
