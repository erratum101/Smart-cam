import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer className="border-t border-white/20 py-14">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex flex-col items-center justify-between gap-8 sm:flex-row">
          <Logo />
          <p className="text-center text-sm text-white/60">
            © {new Date().getFullYear()} Smart Cam. Все права защищены.
          </p>
          <div className="flex gap-6 text-sm text-white/60">
            <a href="#features" className="transition hover:text-white">
              Возможности
            </a>
            <a href="#pricing" className="transition hover:text-white">
              Тарифы
            </a>
            <a href="mailto:support@smartcam.app" className="transition hover:text-white">
              Контакты
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
