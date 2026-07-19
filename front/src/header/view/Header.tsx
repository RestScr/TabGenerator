import { useState } from 'react'
import type { User } from '../model'
import { UploadTabModal } from '../uploadTab/view/UploadTabModal'
import './Header.css'

type HeaderProps = {
  user: User
  onLogoClick?: () => void
  onOpenTab?: (tabId: string) => void
  showSearch?: boolean
}

export function Header({ onLogoClick, onOpenTab, showSearch = true, user }: HeaderProps) {
  const [isUploadOpen, setIsUploadOpen] = useState(false)

  return (
    <>
      <header className="app-header">
        <button className="brand" type="button" aria-label="На главную" onClick={onLogoClick}>
          <div className="brand-mark">♬</div>
          <div className="brand-name">
            Tab<span>Space</span>
          </div>
        </button>

        <div className={showSearch ? 'header-search-wrap is-visible' : 'header-search-wrap'}>
          <label className="header-search">
            <span className="header-search-icon" aria-hidden="true"></span>
            <input
              aria-label="Поиск табов, песен и исполнителей"
              type="search"
              placeholder="Поиск табов, песен, исполнителей..."
              tabIndex={showSearch ? 0 : -1}
            />
            <kbd>⌘K</kbd>
          </label>
        </div>

        <nav className="top-nav" aria-label="Основная навигация">
          <a href="#library">
            <span className="nav-icon">▣</span>
            Моя библиотека
          </a>
          <button className="top-nav-action" type="button" onClick={() => setIsUploadOpen(true)}>
            <span className="nav-icon solid"></span>
            Загрузить таб
          </button>
        </nav>

        <button className="user-menu" type="button" aria-label="Профиль">
          <span className="avatar">{user.initials}</span>
          <span className="user-name">{user.name}</span>
          <span className="chevron" aria-hidden="true"></span>
        </button>
      </header>
      <UploadTabModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onTabReady={(tabId) => onOpenTab?.(tabId)}
      />
    </>
  )
}
