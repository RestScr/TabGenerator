import type { FilterGroup, SidebarLink } from './types'

export const filterGroups: FilterGroup[] = [
  {
    id: 'instrument',
    label: 'Инструмент',
    icon: '⌁',
    value: 'Гитара',
    options: ['Гитара', 'Бас', 'Укулеле'],
  },
  {
    id: 'tuning',
    label: 'Тюнинг',
    icon: '♮',
    value: 'Standard E',
    options: ['Standard E', 'Drop D', 'D Standard'],
  },
  {
    id: 'difficulty',
    label: 'Сложность',
    icon: '▥',
    value: 'Средняя',
    options: ['Все', 'Легкая', 'Средняя', 'Сложная'],
  },
  {
    id: 'tabType',
    label: 'Тип таба',
    icon: '♯',
    value: 'Rhythm',
    options: ['Все', 'Rhythm', 'Lead', 'Acoustic'],
  },
  {
    id: 'genre',
    label: 'Жанр',
    icon: '◇',
    value: 'Rock',
    options: ['Все', 'Rock', 'Metal', 'Alternative', 'Acoustic', 'Blues', 'Pop', 'Jazz'],
  },
]

export const sidebarLinks: SidebarLink[] = [
  { id: 'favorites', label: 'Избранные', icon: '♡' },
  { id: 'recent', label: 'Недавние', icon: '●' },
  { id: 'downloads', label: 'Загрузки', icon: '↓' },
  { id: 'myTabs', label: 'Мои табы', icon: '□' },
]
