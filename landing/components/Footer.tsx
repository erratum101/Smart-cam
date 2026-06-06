import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer className="border-t border-white/5 py-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 sm:flex-row sm:px-6">
        <Logo />
        <p className="text-center text-sm text-white/40">
          © {new Date().getFullYear()} Smart Cam. Все права защищены.
        </p>
        <div className="flex gap-6 text-sm text-white/40">
          <a href="#features" className="hover:text-white">
            Возможности
          </a>
          <a href="#pricing" className="hover:text-white">
            Тарифы
          </a>
          <a href="mailto:support@smartcam.app" className="hover:text-white">
            Контакты
          </a>
        </div>
      </div>
    </footer>
  );
}
