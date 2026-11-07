"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { ArrowLeft, RefreshCw, X } from "lucide-react";

/** Native modal provides inert background, focus containment and Escape. */
export function OfficeWindow({ label, close, back, reload, navigation, children }: {
  label: string; close: () => void; back: () => void; reload: () => Promise<void>; navigation: ReactNode; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return <dialog ref={ref} className="office-tool-window" aria-label={label}
    onCancel={event => {
      // React propagates nested confirmation cancellation through its parent.
      if (event.target !== event.currentTarget) return;
      event.preventDefault(); close();
    }}>
    <header className="office-window-bar">
      <button type="button" className="button" onClick={back} aria-label="Voltar no escritório"><ArrowLeft size={16} />Voltar</button>
      <strong>{label}</strong>
      <button type="button" className="icon-button" onClick={() => void reload()} aria-label="Atualizar workspace"><RefreshCw size={16} aria-hidden="true" /></button>
      <button type="button" className="icon-button" onClick={close} aria-label="Fechar ferramenta" autoFocus><X size={20} /></button>
    </header>
    <nav className="office-window-navigation" aria-label="Trocar ferramenta">{navigation}</nav>
    <div className="office-window-content">{children}</div>
  </dialog>;
}
