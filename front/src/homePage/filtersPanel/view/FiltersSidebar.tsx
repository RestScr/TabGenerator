import type { FilterGroup, SidebarLink } from '../model/types'
import './FiltersSidebar.css'

type FiltersSidebarProps = {
  filters: FilterGroup[]
  links: SidebarLink[]
  values?: Record<string, string>
  activeLink?: string
  onFilterChange?: (id: string, value: string) => void
  onLinkClick?: (id: string) => void
}

export function FiltersSidebar({ activeLink, filters, links, onFilterChange, onLinkClick, values = {} }: FiltersSidebarProps) {
  return (
    <aside className="sidebar" aria-label="Фильтры">
      <h2>Фильтры</h2>

      <div className="filter-list">
        {filters.map((filter) => (
          <div className="filter-field" key={filter.id}>
            <span className="filter-meta">
              <span className="filter-icon" aria-hidden="true">{filter.icon}</span>
              <span id={`filter-label-${filter.id}`}>{filter.label}</span>
            </span>
            <select
              className="select-control"
              aria-labelledby={`filter-label-${filter.id}`}
              value={values[filter.id] ?? filter.value}
              onChange={(event) => onFilterChange?.(filter.id, event.target.value)}
            >
              {filter.options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
        ))}
      </div>

      <nav className="side-links" aria-label="Быстрые разделы">
        {links.map((link) => (
          <a
            className={activeLink === link.id ? 'active' : undefined}
            href={`#${link.id}`}
            key={link.id}
            onClick={() => onLinkClick?.(link.id)}
          >
            <span>{link.icon}</span>
            {link.label}
          </a>
        ))}
      </nav>

      <section className="plus-card">
        <div className="plus-row">
          <span className="plus-icon">✳</span>
          <strong>TabSpace Plus</strong>
        </div>
        <p>Больше функций, офлайн-доступ</p>
        <button type="button">Попробовать бесплатно</button>
      </section>
    </aside>
  )
}
