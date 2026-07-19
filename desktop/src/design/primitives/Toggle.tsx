import { cn } from "../../lib/cn";
import s from "./primitives.module.css";

export interface ToggleProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
}

export function Toggle({ checked, onChange, disabled, id, ...aria }: ToggleProps) {
  return (
    <button
      type="button"
      id={id}
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(s.toggle, checked && s.toggleOn)}
      {...aria}
    >
      <span className={s.toggleKnob} />
    </button>
  );
}
