"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { ArrowLeft, X } from "lucide-react";

/** Native modal provides inert background, focus containment and Escape. */
export function OfficeWindow({ label, close, back, children }: {
  label: string; close: () => void; back: () => void; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return <dialog ref={ref} className="office-tool-window" aria-label={label}
    onCancel={event => { event.preventDefault(); close(); }}>
    <header className="office-window-bar">
      <button type="button" className="button" onClick={back} aria-label="Voltar no escritório"><ArrowLeft size={16} />Voltar</button>
      <strong>{label}</strong>
      <button type="button" className="icon-button" onClick={close} aria-label="Fechar ferramenta" autoFocus><X size={20} /></button>
    </header>
    <div className="office-window-content">{children}</div>
  </dialog>;
}
