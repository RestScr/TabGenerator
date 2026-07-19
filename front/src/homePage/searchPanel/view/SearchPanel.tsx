import './SearchPanel.css'

type SearchPanelProps = {
  genres: string[]
  totalResults: string
  sortLabel: string
  query: string
  selectedGenre: string
  onGenreChange: (genre: string) => void
  onQueryChange: (query: string) => void
  onSortChange: () => void
}

export function SearchPanel({
  genres,
  onGenreChange,
  onQueryChange,
  onSortChange,
  query,
  selectedGenre,
  sortLabel,
  totalResults,
}: SearchPanelProps) {
  return (
    <section className="search-panel">
      <div className="hero-copy">
        <h1>Найти табы</h1>
        <p>Ищи среди миллионов гитарных табулатур</p>
      </div>

      <label className="search-box">
        <span className="search-icon" aria-hidden="true"></span>
        <input
          aria-label="Поиск табов, песен и исполнителей"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Введите название песни или исполнителя..."
        />
      </label>

      <div className="genre-chips" role="group" aria-label="Жанры">
        {genres.map((genre) => (
          <button
            className={genre === selectedGenre ? 'chip active' : 'chip'}
            type="button"
            key={genre}
            onClick={() => onGenreChange(genre)}
          >
            {genre}
          </button>
        ))}
      </div>

      <div className="results-toolbar">
        <span>Найдено результатов: {totalResults}</span>
        <div className="toolbar-actions">
          <button className="sort-button" type="button" aria-label={`Изменить сортировку. Сейчас: ${sortLabel}`} onClick={onSortChange}>
            Сортировка: <strong>{sortLabel}</strong> <span className="sort-chevron" aria-hidden="true"></span>
          </button>
        </div>
      </div>
    </section>
  )
}
