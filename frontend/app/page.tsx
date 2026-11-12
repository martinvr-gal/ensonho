const highlights = [
  { label: "Compra", text: "Casas tradicionais, machiya e proxectos con carácter." },
  { label: "Aluguer", text: "Estadías vacacionais ou aluguer residencial a longo prazo." },
  { label: "Localización", text: "Estacións, servizos e cidades próximas a cada vivenda." },
];

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="/">ensonho</a>
        <nav aria-label="Navegación principal">
          <a href="#explorar">Explorar</a>
          <a href="#publicar">Publicar vivenda</a>
          <a className="button button-small" href="#entrar">Entrar</a>
        </nav>
      </header>

      <section className="hero">
        <p className="eyebrow">Vivendas xaponesas, ao teu ritmo</p>
        <h1>Atopa o teu lugar en Xapón.</h1>
        <p className="hero-copy">
          Un punto de encontro para descubrir, comprar ou alugar vivendas con historia.
        </p>
        <div className="search-bar" id="explorar">
          <input aria-label="Localización" placeholder="Prefectura ou cidade" />
          <select aria-label="Modalidade" defaultValue="all">
            <option value="all">Comprar ou alugar</option>
            <option value="sale">Comprar</option>
            <option value="rent">Alugar</option>
          </select>
          <button className="button" type="button">Buscar vivendas</button>
        </div>
      </section>

      <section className="highlights" aria-label="Servizos">
        {highlights.map((highlight) => (
          <article key={highlight.label}>
            <p className="eyebrow">{highlight.label}</p>
            <p>{highlight.text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
